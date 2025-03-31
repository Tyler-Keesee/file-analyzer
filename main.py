#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Advanced Storage Space Analyzer - High Performance Edition

This cutting-edge application scans a selected drive concurrently,
categorizes files by extension, and displays detailed storage statistics.
It uses an optimized file scanning engine based on os.scandir and a threaded
directory queue for fast collection and processing. The GUI is built with PyQt6.
Additionally, it offers a dedicated view for files larger than 5GB.
"""

import os
import sys
import json
import shutil
import datetime
import logging
import threading
from queue import Queue
from concurrent.futures import ThreadPoolExecutor

import psutil
from PyQt6.QtWidgets import (
    QMainWindow, QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QPushButton, QProgressBar, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QFileDialog, QMessageBox, QMenu, QAbstractItemView, QDialog, QListWidget
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer

# =============================================================================
# Manual Override for Tcl/Tk Paths (for proper PyQt operation)
# =============================================================================
python_path = sys.executable
python_dir = os.path.dirname(python_path)
if os.path.exists(os.path.join(python_dir, 'tcl')):
    os.environ['TCL_LIBRARY'] = os.path.join(python_dir, 'tcl', 'tcl8.6')
    os.environ['TK_LIBRARY'] = os.path.join(python_dir, 'tcl', 'tk8.6')
else:
    # Try common locations
    common_locations = [
        r"C:\Program Files\Python312\tcl",
        r"C:\Program Files\Python311\tcl",
        r"C:\Program Files\Python310\tcl",
        r"C:\Python312\tcl",
        r"C:\Python311\tcl",
        r"C:\Python310\tcl",
        r"C:\Users\ty\AppData\Local\Programs\Python\Python313\tcl"
    ]
    for location in common_locations:
        if os.path.exists(location):
            os.environ['TCL_LIBRARY'] = os.path.join(location, 'tcl8.6')
            os.environ['TK_LIBRARY'] = os.path.join(location, 'tk8.6')
            break

# =============================================================================
# Logging Setup
# =============================================================================
log_file = 'main.log'
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logging.info("Application starting")
logging.info(f"Python executable: {python_path}")
logging.info(f"Python directory: {python_dir}")
if 'TCL_LIBRARY' in os.environ and 'TK_LIBRARY' in os.environ:
    logging.info(f"TCL_LIBRARY set to: {os.environ['TCL_LIBRARY']}")
    logging.info(f"TK_LIBRARY set to: {os.environ['TK_LIBRARY']}")
else:
    logging.warning("Tcl/Tk paths not set; trying common locations")
    common_locations = [
        r"C:\Program Files\Python312\tcl",
        r"C:\Program Files\Python311\tcl",
        r"C:\Program Files\Python310\tcl",
        r"C:\Python312\tcl",
        r"C:\Python311\tcl",
        r"C:\Python310\tcl"
    ]
    for location in common_locations:
        if os.path.exists(location):
            os.environ['TCL_LIBRARY'] = os.path.join(location, 'tcl8.6')
            os.environ['TK_LIBRARY'] = os.path.join(location, 'tk8.6')
            logging.info(f"TCL_LIBRARY set to: {os.environ['TCL_LIBRARY']}")
            logging.info(f"TK_LIBRARY set to: {os.environ['TK_LIBRARY']}")
            break

# =============================================================================
# Optimized Concurrent Directory Traversal with os.scandir
# =============================================================================
def concurrent_scan(root, excluded_paths, stop_requested):
    """
    Recursively scans directories starting at root using os.scandir,
    processing directories concurrently via a shared Queue.
    Returns a list of file details (dict with keys: path, size, name, ext).
    """
    file_details = []
    dir_queue = Queue()
    dir_queue.put(root)
    lock = threading.Lock()

    def worker():
        while not stop_requested() and not dir_queue.empty():
            try:
                current_dir = dir_queue.get(timeout=1)
            except Exception:
                break
            try:
                with os.scandir(current_dir) as entries:
                    for entry in entries:
                        if stop_requested():
                            break
                        if entry.is_file(follow_symlinks=False):
                            try:
                                size = entry.stat(follow_symlinks=False).st_size
                            except Exception:
                                continue
                            file_details.append({
                                "path": os.path.join(current_dir, entry.name),
                                "size": size,
                                "name": entry.name,
                                "ext": os.path.splitext(entry.name)[1].lower()
                            })
                        elif entry.is_dir(follow_symlinks=False):
                            # Skip excluded or system directories.
                            skip = False
                            for excl in excluded_paths:
                                if excl in entry.path:
                                    skip = True
                                    break
                            if skip:
                                continue
                            if any(s in entry.path.lower() for s in ["$recycle.bin", "system volume information"]):
                                continue
                            dir_queue.put(entry.path)
            except Exception as e:
                logging.error(f"Error scanning {current_dir}: {e}")
            finally:
                dir_queue.task_done()

    num_threads = min(32, os.cpu_count() * 2) if os.cpu_count() else 4
    threads = []
    for _ in range(num_threads):
        t = threading.Thread(target=worker, daemon=True)
        t.start()
        threads.append(t)
    dir_queue.join()
    for t in threads:
        t.join()
    return file_details

# =============================================================================
# High-Performance File Scanner Class
# =============================================================================
class FastScanner:
    """High-performance file scanner using multiple threads and optimized algorithms."""
    def __init__(self, drive, excluded_paths=None, min_file_size=1024*1024):
        self.drive = drive
        self.excluded_paths = excluded_paths or []
        self.min_file_size = min_file_size
        self.stop_requested = False
        self.files_processed = 0
        self.bytes_processed = 0

    def scan(self, callback=None, progress_callback=None):
        """
        Perform a fast scan of the drive.

        Args:
            callback: Function to call with each file (path, size, name, category)
            progress_callback: Function to call with progress updates (files_processed, bytes_processed)

        Returns:
            Tuple of (total_files_processed, total_bytes)
        """
        start_time = datetime.datetime.now()
        self.files_processed = 0
        self.bytes_processed = 0

        # Use the concurrent_scan function for fast file collection.
        files = concurrent_scan(self.drive + "\\", self.excluded_paths, lambda: self.stop_requested)
        total_files = len(files)

        # Process files in a loop.
        for i, f in enumerate(files):
            if self.stop_requested:
                break
            try:
                size = f["size"]
                if size < self.min_file_size:
                    self.files_processed += 1
                    continue
                # Update counters.
                self.files_processed += 1
                self.bytes_processed += size
                # Call the provided callback with file details.
                if callback:
                    # Here, a simple callback without categorization.
                    callback(f["path"], size, f["name"], None)
                # Periodically update progress.
                if progress_callback and i % 100 == 0:
                    progress_callback(self.files_processed, self.bytes_processed)
            except Exception as e:
                logging.error(f"Error processing file {f['path']}: {e}")
        duration = (datetime.datetime.now() - start_time).total_seconds()
        logging.info(f"FastScanner: Processed {self.files_processed} files, {self.bytes_processed/(1024**3):.2f} GB in {duration:.2f}s")
        return self.files_processed, self.bytes_processed

# =============================================================================
# Optimized ScanWorker Using FastScanner and Concurrent Scan
# =============================================================================
class ScanWorker(QThread):
    progress_update = pyqtSignal(str, int, float, float, float)  # (status, progress%, elapsed, ETA, rate)
    scan_finished = pyqtSignal(dict, int, int, float)  # (categories, total_bytes, processed_count, duration)

    def __init__(self, drive, settings):
        super().__init__()
        self.drive = drive
        self.settings = settings
        self.stop_requested = False
        logging.info(f"ScanWorker initialized for drive {drive}")

    def run(self):
        start_time = datetime.datetime.now()
        excluded_paths = self.settings.get("excluded_paths", [])
        # Define extension mappings.
        extension_categories = {
            '.exe': 'Programs', '.msi': 'Programs', '.bat': 'Programs', '.dll': 'Programs',
            '.app': 'Programs', '.com': 'Programs', '.jar': 'Programs', '.cmd': 'Programs',
            '.unity3d': 'Games', '.u3d': 'Games', '.pak': 'Games', '.uasset': 'Games',
            '.sav': 'Games', '.gam': 'Games', '.game': 'Games',
            '.pdf': 'Documents', '.doc': 'Documents', '.docx': 'Documents', '.txt': 'Documents',
            '.xlsx': 'Documents', '.pptx': 'Documents', '.odt': 'Documents', '.rtf': 'Documents',
            '.md': 'Documents', '.csv': 'Documents', '.json': 'Documents', '.xml': 'Documents',
            '.jpg': 'Media', '.jpeg': 'Media', '.png': 'Media', '.gif': 'Media',
            '.mp3': 'Media', '.mp4': 'Media', '.avi': 'Media', '.mov': 'Media',
            '.wav': 'Media', '.flac': 'Media', '.mkv': 'Media', '.webm': 'Media',
            '.webp': 'Media', '.bmp': 'Media', '.tiff': 'Media', '.svg': 'Media',
            '.zip': 'Archives', '.rar': 'Archives', '.7z': 'Archives', '.tar': 'Archives',
            '.gz': 'Archives', '.bz2': 'Archives', '.iso': 'Archives', '.cab': 'Archives',
            '.sys': 'System', '.ini': 'System', '.log': 'System', '.tmp': 'System',
            '.reg': 'System', '.config': 'System', '.dat': 'System', '.bin': 'System'
        }
        game_dirs = ["steam", "epic games", "games", "ubisoft", "origin", "battle.net",
                     "gog", "ea games", "minecraft", "rockstar games", "call of duty", "overwatch"]
        program_dirs = ["program files", "program files (x86)", "programdata", "apps", "applications", "software", "programs"]

        # Use FastScanner to collect files.
        scanner = FastScanner(self.drive, excluded_paths, min_file_size=1024*1024)
        files_processed, _ = scanner.scan()  # We collect files and update counters internally.
        # Now use concurrent_scan to get file details for categorization.
        files = concurrent_scan(f"{self.drive}\\", excluded_paths, lambda: self.stop_requested)
        total_files = len(files)
        # Update progress: files collected.
        elapsed = (datetime.datetime.now() - start_time).total_seconds()
        self.progress_update.emit("Files collected", 20, elapsed, 0, total_files / elapsed if elapsed > 0 else 0)

        total_bytes = 0
        processed_count = 0
        categories = {
            "Programs": {"size": 0, "count": 0, "paths": []},
            "Games": {"size": 0, "count": 0, "paths": []},
            "Documents": {"size": 0, "count": 0, "paths": []},
            "Media": {"size": 0, "count": 0, "paths": []},
            "Archives": {"size": 0, "count": 0, "paths": []},
            "System": {"size": 0, "count": 0, "paths": []},
            "Other": {"size": 0, "count": 0, "paths": []}
        }
        # Process and categorize files.
        for i, f in enumerate(files):
            if self.stop_requested:
                logging.info("Scan cancelled by user.")
                return
            size = f["size"]
            if size < 1024 * 1024:  # Skip files under 1MB
                continue
            ext = f["ext"]
            category = extension_categories.get(ext, "Other")
            if ext == '.exe':
                if any(g in f["path"].lower() for g in game_dirs):
                    category = "Games"
                elif any(p in f["path"].lower() for p in program_dirs):
                    category = "Programs"
            categories[category]["size"] += size
            categories[category]["count"] += 1
            categories[category]["paths"].append({
                "path": f["path"],
                "size": size,
                "name": f["name"]
            })
            total_bytes += size
            processed_count += 1
            # Update progress every 100 files.
            if i % 100 == 0 and i > 0:
                now = datetime.datetime.now()
                elapsed = (now - start_time).total_seconds()
                rate = i / elapsed if elapsed > 0 else 0
                remaining = total_files - i
                eta = remaining / rate if rate > 0 else 0
                progress_val = 20 + min(75, int((i / total_files) * 75))
                status = f"Processing {i}/{total_files} files | Elapsed: {elapsed:.1f}s | ETA: {eta:.1f}s"
                self.progress_update.emit(status, progress_val, elapsed, eta, rate)
        duration = (datetime.datetime.now() - start_time).total_seconds()
        logging.info(f"Scan complete: {processed_count} files processed, {total_bytes/(1024**3):.2f} GB in {duration:.2f}s")
        self.scan_finished.emit(categories, total_bytes, processed_count, duration)

    def stop(self):
        logging.info("Stop requested for ScanWorker.")
        self.stop_requested = True

# =============================================================================
# Main Application Window with "Files > 5GB" Feature
# =============================================================================
class StorageAnalyzer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Advanced Storage Space Analyzer")
        self.resize(1200, 800)
        self.settings = self.load_settings()
        self.categories = {
            "Programs": {"size": 0, "count": 0, "paths": []},
            "Games": {"size": 0, "count": 0, "paths": []},
            "Documents": {"size": 0, "count": 0, "paths": []},
            "Media": {"size": 0, "count": 0, "paths": []},
            "Archives": {"size": 0, "count": 0, "paths": []},
            "System": {"size": 0, "count": 0, "paths": []},
            "Other": {"size": 0, "count": 0, "paths": []}
        }
        self.worker = None
        logging.info("StorageAnalyzer initialized")
        self.initUI()

    def initUI(self):
        logging.info("Initializing UI...")
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        
        # Top control panel
        controls_layout = QHBoxLayout()
        main_layout.addLayout(controls_layout)
        
        drive_label = QLabel("Storage Location:")
        controls_layout.addWidget(drive_label)
        self.drive_combo = QComboBox()
        drives = [f"{d}:" for d in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' if os.path.exists(f"{d}:")]
        self.drive_combo.addItems(drives)
        logging.info(f"Drives found: {drives}")
        controls_layout.addWidget(self.drive_combo)
        
        category_label = QLabel("File Categories:")
        controls_layout.addWidget(category_label)
        # Add "Files > 5GB" as a special category along with existing ones.
        cat_list = ["All Categories", "Files > 5GB"] + list(self.categories.keys())
        self.category_combo = QComboBox()
        self.category_combo.addItems(cat_list)
        self.category_combo.currentIndexChanged.connect(self.filter_by_category)
        controls_layout.addWidget(self.category_combo)
        
        self.category_info = QLabel("")
        controls_layout.addWidget(self.category_info)
        
        # Action buttons
        buttons_layout = QHBoxLayout()
        main_layout.addLayout(buttons_layout)
        self.scan_btn = QPushButton("Scan Files")
        self.scan_btn.clicked.connect(self.start_scan)
        buttons_layout.addWidget(self.scan_btn)
        
        self.export_btn = QPushButton("Export List")
        self.export_btn.clicked.connect(self.export_list)
        buttons_layout.addWidget(self.export_btn)
        
        self.exclusions_btn = QPushButton("Manage Exclusions")
        self.exclusions_btn.clicked.connect(self.manage_exclusions)
        buttons_layout.addWidget(self.exclusions_btn)
        
        self.backup_btn = QPushButton("Backup Selected")
        self.backup_btn.clicked.connect(self.backup_files)
        buttons_layout.addWidget(self.backup_btn)
        
        self.delete_btn = QPushButton("Delete Selected")
        self.delete_btn.clicked.connect(self.delete_multiple)
        buttons_layout.addWidget(self.delete_btn)
        
        # Progress bar and search controls
        progress_search_layout = QHBoxLayout()
        main_layout.addLayout(progress_search_layout)
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")
        progress_search_layout.addWidget(self.progress_bar)
        
        self.eta_label = QLabel("ETA: N/A")
        progress_search_layout.addWidget(self.eta_label)
        
        search_label = QLabel("Search:")
        progress_search_layout.addWidget(search_label)
        self.search_edit = QLineEdit()
        self.search_edit.textChanged.connect(self.filter_items)
        progress_search_layout.addWidget(self.search_edit)
        
        # File list table
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Size", "Name", "Location"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        main_layout.addWidget(self.table)
        
        # Statistics label
        self.stats_label = QLabel("")
        main_layout.addWidget(self.stats_label)
        
        self.statusBar().showMessage("Ready")

    def load_settings(self):
        try:
            with open('settings.json', 'r') as f:
                settings = json.load(f)
                logging.info("Settings loaded.")
                return settings
        except Exception as e:
            logging.warning(f"Could not load settings: {e}")
            return {"last_scan": None, "excluded_paths": []}

    def save_settings(self):
        try:
            with open('settings.json', 'w') as f:
                json.dump(self.settings, f)
            logging.info("Settings saved.")
        except Exception as e:
            logging.error(f"Error saving settings: {e}")

    def export_list(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export List", "", "Text files (*.txt);;CSV files (*.csv)")
        if path:
            try:
                with open(path, 'w') as f:
                    category = self.category_combo.currentText()
                    f.write(f"Storage Analysis Results - {category}\n")
                    f.write("=" * 80 + "\n")
                    f.write("Size | Name | Location\n")
                    f.write("-" * 80 + "\n")
                    for row in range(self.table.rowCount()):
                        row_data = [self.table.item(row, col).text() for col in range(self.table.columnCount())]
                        f.write(" | ".join(row_data) + "\n")
                QMessageBox.information(self, "Export", "Export successful!")
            except Exception as e:
                QMessageBox.warning(self, "Export Error", str(e))

    def manage_exclusions(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Manage Exclusions")
        dialog.resize(500, 400)
        layout = QVBoxLayout(dialog)
        list_widget = QListWidget()
        for path in self.settings.get("excluded_paths", []):
            list_widget.addItem(path)
        layout.addWidget(list_widget)
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("Add Path")
        remove_btn = QPushButton("Remove Selected")
        close_btn = QPushButton("Close")
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(remove_btn)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        def add_path():
            p = QFileDialog.getExistingDirectory(dialog, "Select Directory to Exclude")
            if p and p not in self.settings.get("excluded_paths", []):
                list_widget.addItem(p)
                self.settings.setdefault("excluded_paths", []).append(p)
                self.save_settings()

        def remove_path():
            row = list_widget.currentRow()
            if row >= 0:
                item = list_widget.takeItem(row)
                self.settings["excluded_paths"].remove(item.text())
                self.save_settings()

        add_btn.clicked.connect(add_path)
        remove_btn.clicked.connect(remove_path)
        close_btn.clicked.connect(dialog.accept)
        dialog.exec()

    def backup_files(self):
        selected_rows = {index.row() for index in self.table.selectedIndexes()}
        if not selected_rows:
            QMessageBox.warning(self, "Warning", "Please select files to backup")
            return
        backup_dir = QFileDialog.getExistingDirectory(self, "Select Backup Directory")
        if backup_dir:
            success_count = 0
            error_count = 0
            for row in selected_rows:
                name = self.table.item(row, 1).text().strip()
                location = self.table.item(row, 2).text().strip()
                file_path = os.path.join(location, name)
                try:
                    if os.path.isfile(file_path):
                        shutil.copy2(file_path, os.path.join(backup_dir, os.path.basename(file_path)))
                        success_count += 1
                    elif os.path.isdir(file_path):
                        target_dir = os.path.join(backup_dir, os.path.basename(file_path))
                        shutil.copytree(file_path, target_dir)
                        success_count += 1
                except Exception as e:
                    error_count += 1
                    logging.error(f"Backup error: {e}")
            QMessageBox.information(self, "Backup Complete",
                                    f"Successfully backed up {success_count} items.\nFailed to backup {error_count} items.")

    def delete_multiple(self):
        selected_rows = {index.row() for index in self.table.selectedIndexes()}
        if not selected_rows:
            QMessageBox.warning(self, "Warning", "Please select files to delete")
            return
        if QMessageBox.question(self, "Confirm Delete",
                                f"Delete {len(selected_rows)} selected items? This cannot be undone.",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            success_count = 0
            error_count = 0
            for row in sorted(selected_rows, reverse=True):
                name = self.table.item(row, 1).text().strip()
                location = self.table.item(row, 2).text().strip()
                file_path = os.path.join(location, name)
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                        success_count += 1
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                        success_count += 1
                    else:
                        error_count += 1
                    self.table.removeRow(row)
                except PermissionError:
                    error_count += 1
                    QMessageBox.warning(self, "Permission Denied",
                                        f"Unable to delete {file_path}\nTry running as administrator")
                except Exception as e:
                    error_count += 1
                    logging.error(f"Delete error: {e}")
            self.filter_by_category()
            QMessageBox.information(self, "Delete Complete",
                                    f"Successfully deleted {success_count} items.\nFailed to delete {error_count} items.")

    def open_location(self):
        selected_rows = {index.row() for index in self.table.selectedIndexes()}
        if selected_rows:
            row = next(iter(selected_rows))
            name = self.table.item(row, 1).text().strip()
            location = self.table.item(row, 2).text().strip()
            file_path = os.path.join(location, name)
            if os.path.exists(file_path):
                os.system(f'explorer /select,"{file_path}"')
            else:
                if os.path.exists(location):
                    os.system(f'explorer "{location}"')
                else:
                    QMessageBox.information(self, "Info", "Path no longer exists")

    def show_context_menu(self, pos):
        menu = QMenu()
        open_act = menu.addAction("Open Location")
        delete_act = menu.addAction("Delete")
        backup_act = menu.addAction("Backup")
        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if action == open_act:
            self.open_location()
        elif action == delete_act:
            self.delete_multiple()
        elif action == backup_act:
            self.backup_files()

    def start_scan(self):
        self.table.setRowCount(0)
        self.progress_bar.setValue(0)
        self.eta_label.setText("ETA: Calculating...")
        # Reset categories
        for key in self.categories:
            self.categories[key]["size"] = 0
            self.categories[key]["count"] = 0
            self.categories[key]["paths"] = []
        self.scan_btn.setEnabled(False)
        self.statusBar().showMessage("Scanning...")
        drive = self.drive_combo.currentText()
        self.worker = ScanWorker(drive, self.settings)
        self.worker.progress_update.connect(self.update_progress)
        self.worker.scan_finished.connect(self.scan_complete)
        self.worker.start()

    def update_progress(self, status, progress_val, elapsed, eta, rate):
        self.statusBar().showMessage(status)
        self.progress_bar.setValue(progress_val)
        self.eta_label.setText(f"ETA: {eta:.1f}s | Rate: {rate:.1f} f/s | Elapsed: {elapsed:.1f}s")

    def scan_complete(self, categories, total_bytes, processed_count, duration):
        self.categories = categories
        self.display_categories()
        self.update_stats(total_bytes, processed_count, duration)
        self.settings["last_scan"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.save_settings()
        self.progress_bar.setValue(100)
        self.scan_btn.setEnabled(True)
        self.statusBar().showMessage(f"Scan complete. Processed {processed_count} files.")
        QMessageBox.information(self, "Scan Complete",
                                f"Analyzed {processed_count} files on drive {self.drive_combo.currentText()}\n"
                                f"Total size: {round(total_bytes/(1024**3), 2)} GB\n"
                                f"Scan duration: {round(duration, 2)} seconds")

    def display_categories(self):
        self.table.setRowCount(0)
        selected_category = self.category_combo.currentText()
        # "Files > 5GB" view: aggregate all file paths over 5GB.
        if selected_category == "Files > 5GB":
            all_large_files = []
            threshold = 5 * 1024**3  # 5GB in bytes
            for cat in self.categories.values():
                for file_data in cat["paths"]:
                    if file_data["size"] >= threshold:
                        all_large_files.append(file_data)
            sorted_files = sorted(all_large_files, key=lambda x: x["size"], reverse=True)
            for file_data in sorted_files:
                row = self.table.rowCount()
                self.table.insertRow(row)
                size = file_data["size"]
                size_val = round(size/(1024**3), 2)
                item1 = QTableWidgetItem(f"{size_val:6.2f} GB")
                item2 = QTableWidgetItem(file_data["name"])
                item3 = QTableWidgetItem(os.path.dirname(file_data["path"]))
                self.table.setItem(row, 0, item1)
                self.table.setItem(row, 1, item2)
                self.table.setItem(row, 2, item3)
        elif selected_category == "All Categories":
            for category_name, data in self.categories.items():
                row = self.table.rowCount()
                self.table.insertRow(row)
                size_gb = round(data["size"]/(1024**3), 2)
                item1 = QTableWidgetItem(f"{size_gb:6.2f} GB")
                item2 = QTableWidgetItem(category_name)
                item3 = QTableWidgetItem(f"{data['count']} items")
                self.table.setItem(row, 0, item1)
                self.table.setItem(row, 1, item2)
                self.table.setItem(row, 2, item3)
        else:
            data = self.categories.get(selected_category, {"paths": []})
            sorted_items = sorted(data["paths"], key=lambda x: x["size"], reverse=True)
            for file_data in sorted_items:
                row = self.table.rowCount()
                self.table.insertRow(row)
                size = file_data["size"]
                if size > 1024**3:
                    size_val = round(size/(1024**3), 2)
                    unit = "GB"
                else:
                    size_val = round(size/(1024**2), 2)
                    unit = "MB"
                item1 = QTableWidgetItem(f"{size_val:6.2f} {unit}")
                item2 = QTableWidgetItem(file_data["name"])
                item3 = QTableWidgetItem(os.path.dirname(file_data["path"]))
                self.table.setItem(row, 0, item1)
                self.table.setItem(row, 1, item2)
                self.table.setItem(row, 2, item3)

    def filter_by_category(self):
        self.display_categories()
        selected_category = self.category_combo.currentText()
        if selected_category == "All Categories":
            total_size = sum(cat["size"] for cat in self.categories.values())
            total_count = sum(cat["count"] for cat in self.categories.values())
            size_gb = round(total_size/(1024**3), 2)
            self.category_info.setText(f"Total: {size_gb} GB, {total_count} items")
        elif selected_category == "Files > 5GB":
            total_large = 0
            total_large_size = 0
            threshold = 5 * 1024**3
            for cat in self.categories.values():
                for f in cat["paths"]:
                    if f["size"] >= threshold:
                        total_large += 1
                        total_large_size += f["size"]
            size_gb = round(total_large_size/(1024**3), 2)
            self.category_info.setText(f"Files > 5GB: {total_large} items, {size_gb} GB total")
        else:
            data = self.categories.get(selected_category, {"size": 0, "count": 0})
            size_gb = round(data["size"]/(1024**3), 2)
            self.category_info.setText(f"Total: {size_gb} GB, {data['count']} items")

    def filter_items(self):
        search_term = self.search_edit.text().lower()
        for row in range(self.table.rowCount()):
            name_item = self.table.item(row, 1)
            location_item = self.table.item(row, 2)
            text = (name_item.text() + " " + location_item.text()).lower()
            self.table.setRowHidden(row, search_term not in text)

    def update_stats(self, total_bytes, total_count, duration):
        drive = self.drive_combo.currentText()
        try:
            usage = psutil.disk_usage(drive)
            drive_total = round(usage.total/(1024**3), 2)
            drive_used = round(usage.used/(1024**3), 2)
            drive_free = round(usage.free/(1024**3), 2)
            drive_percent = usage.percent
        except Exception as e:
            logging.error(f"Error getting disk usage: {e}")
            drive_total = drive_used = drive_free = drive_percent = 0
        stats_text = (f"Drive {drive}: {drive_used} GB used of {drive_total} GB ({drive_percent}% full), {drive_free} GB free\n"
                      f"Scanned: {round(total_bytes/(1024**3), 2)} GB in {total_count} files (Scan time: {round(duration, 2)} seconds)\n"
                      f"Category distribution: " +
                      ", ".join([f"{cat}: {round((v['size']/total_bytes)*100, 2)}%" 
                                 for cat, v in self.categories.items() if total_bytes > 0 and v['count'] > 0]))
        self.stats_label.setText(stats_text)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = StorageAnalyzer()
    window.show()
    sys.exit(app.exec())
