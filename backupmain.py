import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter.font import Font
import threading
import shutil
import json
import datetime
import winreg
from pathlib import Path

class StorageAnalyzer(tk.Tk):  # Changed from GameAnalyzer to StorageAnalyzer
    def __init__(self):
        super().__init__()
        
        self.title("Advanced Storage Space Analyzer")  # Updated title
        self.geometry("1200x800")
        self.configure(bg='#f0f0f0')
        
        # Initialize settings
        self.settings = self.load_settings()
        
        # Initialize categories
        self.categories = {
            "Programs": {"size": 0, "count": 0, "paths": []},
            "Games": {"size": 0, "count": 0, "paths": []},
            "Documents": {"size": 0, "count": 0, "paths": []},
            "Media": {"size": 0, "count": 0, "paths": []},
            "Archives": {"size": 0, "count": 0, "paths": []},
            "System": {"size": 0, "count": 0, "paths": []},
            "Other": {"size": 0, "count": 0, "paths": []}
        }
        
        # Rest of UI initialization...        
        # Main container with modern styling
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        self.main_frame = ttk.Frame(self)
        self.main_frame.pack(padx=20, pady=20, fill=tk.BOTH, expand=True)
        
        # Drive selection with enhanced UI
        self.drive_frame = ttk.LabelFrame(self.main_frame, text="Storage Location")
        self.drive_frame.pack(fill=tk.X, pady=5)
        self.drives = [f"{d}:" for d in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' if os.path.exists(f'{d}:')]
        self.drive_var = tk.StringVar(value=self.drives[0] if self.drives else "C:")
        self.drive_menu = ttk.Combobox(self.drive_frame, textvariable=self.drive_var, values=self.drives)
        self.drive_menu.pack(padx=5, pady=5, fill=tk.X)
        
        # Control panel
        self.control_frame = ttk.Frame(self.main_frame)
        self.control_frame.pack(fill=tk.X, pady=10)
        
        # Enhanced scan button
        self.scan_btn = ttk.Button(self.control_frame, text="Scan Games", command=self.start_scan)
        self.scan_btn.pack(side=tk.LEFT, padx=5)
        
        # Export functionality
        self.export_btn = ttk.Button(self.control_frame, text="Export List", command=self.export_list)
        self.export_btn.pack(side=tk.LEFT, padx=5)
        
        # Statistics display
        self.stats_frame = ttk.LabelFrame(self.main_frame, text="Statistics")
        self.stats_frame.pack(fill=tk.X, pady=5)
        self.stats_label = ttk.Label(self.stats_frame, text="")
        self.stats_label.pack(pady=5)
        
        # Enhanced progress tracking
        self.progress = ttk.Progressbar(self.main_frame, mode='determinate')
        self.progress.pack(fill=tk.X, pady=10)
        
        # Search functionality
        self.search_frame = ttk.Frame(self.main_frame)
        self.search_frame.pack(fill=tk.X, pady=5)
        ttk.Label(self.search_frame, text="Search:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.filter_games)
        self.search_entry = ttk.Entry(self.search_frame, textvariable=self.search_var)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Games list with enhanced display
        self.games_frame = ttk.LabelFrame(self.main_frame, text="Games List")
        self.games_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Column headers
        self.headers_frame = ttk.Frame(self.games_frame)
        self.headers_frame.pack(fill=tk.X)
        ttk.Label(self.headers_frame, text="Size (GB)", width=15).pack(side=tk.LEFT)
        ttk.Label(self.headers_frame, text="Game Name", width=40).pack(side=tk.LEFT)
        ttk.Label(self.headers_frame, text="Location", width=30).pack(side=tk.LEFT)
        
        # Enhanced scrollbar
        self.scrollbar = ttk.Scrollbar(self.games_frame)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Enhanced listbox with better formatting
        self.games_list = tk.Listbox(self.games_frame, 
                                    yscrollcommand=self.scrollbar.set,
                                    font=('Consolas', 10),
                                    selectmode=tk.EXTENDED,
                                    bg='white',
                                    height=20)
        self.games_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.config(command=self.games_list.yview)
        
        # Action buttons frame
        self.action_frame = ttk.Frame(self.main_frame)
        self.action_frame.pack(fill=tk.X, pady=10)
        
        # Enhanced delete button
        self.delete_btn = ttk.Button(self.action_frame, text="Delete Selected",
                                   command=self.delete_multiple)
        self.delete_btn.pack(side=tk.LEFT, padx=5)
        
        # Backup functionality
        self.backup_btn = ttk.Button(self.action_frame, text="Backup Selected",
                                   command=self.backup_games)
        self.backup_btn.pack(side=tk.LEFT, padx=5)
        
        # Right-click context menu
        self.create_context_menu()
        
        self.games = []
        self.total_size = 0
        
    def load_settings(self):
        try:
            with open('settings.json', 'r') as f:
                return json.load(f)
        except:
            return {"last_scan": None, "excluded_paths": []}
            
    def create_context_menu(self):
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Open Location", command=self.open_location)
        self.context_menu.add_command(label="Delete", command=self.delete_multiple)
        self.context_menu.add_command(label="Backup", command=self.backup_games)
        self.games_list.bind("<Button-3>", self.show_context_menu)
        
    def show_context_menu(self, event):
        self.context_menu.tk_popup(event.x_root, event.y_root)
        
    def open_location(self):
        selection = self.games_list.curselection()
        if selection:
            game_path = self.games_list.get(selection[0]).split(" | ")[2].strip()
            os.system(f'explorer /select,"{game_path}"')
            
    def get_size(self, path):
        """Optimized version of get_size that uses os.scandir for better performance"""
        try:
            if os.path.isfile(path):
                return os.path.getsize(path)
                
            total_size = 0
            with os.scandir(path) as it:
                for entry in it:
                    try:
                        if entry.is_file():
                            total_size += entry.stat().st_size
                        elif entry.is_dir():
                            total_size += self.get_size(entry.path)
                    except (OSError, FileNotFoundError, PermissionError):
                        continue
                        
            return total_size
        except Exception:
            return 0            
    def filter_games(self, *args):
        search_term = self.search_var.get().lower()
        self.games_list.delete(0, tk.END)
        for game in self.games:
            if search_term in game.lower():
                size = self.get_size(game)
                size_gb = round(size / (1024**3), 2)
                game_name = os.path.basename(game)
                location = os.path.dirname(game)
                self.games_list.insert(tk.END, f"{size_gb:8.2f} GB | {game_name:<40} | {location}")
                
    def export_list(self):
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("CSV files", "*.csv")]
        )
        if file_path:
            with open(file_path, 'w') as f:
                f.write("Size (GB) | Game Name | Location\n")
                f.write("-" * 80 + "\n")
                for idx in range(self.games_list.size()):
                    f.write(f"{self.games_list.get(idx)}\n")
                    
    def backup_games(self):
        selections = self.games_list.curselection()
        if not selections:
            messagebox.showwarning("Warning", "Please select games to backup")
            return
            
        backup_dir = filedialog.askdirectory(title="Select Backup Directory")
        if backup_dir:
            for idx in selections:
                game_path = self.games_list.get(idx).split(" | ")[2].strip()
                try:
                    if os.path.isfile(game_path):
                        shutil.copy2(game_path, backup_dir)
                    else:
                        shutil.copytree(game_path, 
                                      os.path.join(backup_dir, os.path.basename(game_path)))
                except Exception as e:
                    messagebox.showerror("Backup Error", str(e))
            messagebox.showinfo("Success", "Backup completed")
            
    def start_scan(self):
        self.games_list.delete(0, tk.END)
        self.progress['value'] = 0
        self.games = []
        self.total_size = 0
        threading.Thread(target=self.scan_games, daemon=True).start()
        
    def scan_files(self):
        try:
            selected_drive = self.drive_var.get()
            
            # Reset categories
            for category in self.categories.values():
                category["size"] = 0
                category["count"] = 0
                category["paths"] = []
            
            self.all_files = []
            total_scanned = 0
            
            # Create file extension mappings
            extension_categories = {
                # Programs
                '.exe': 'Programs', '.msi': 'Programs', '.bat': 'Programs', '.dll': 'Programs',
                '.app': 'Programs', '.com': 'Programs', '.jar': 'Programs', '.cmd': 'Programs',
                
                # Games
                '.unity3d': 'Games', '.u3d': 'Games', '.pak': 'Games', '.uasset': 'Games',
                '.sav': 'Games', '.gam': 'Games', '.game': 'Games',
                
                # Documents
                '.pdf': 'Documents', '.doc': 'Documents', '.docx': 'Documents', '.txt': 'Documents',
                '.xlsx': 'Documents', '.pptx': 'Documents', '.odt': 'Documents', '.rtf': 'Documents',
                '.md': 'Documents', '.csv': 'Documents', '.json': 'Documents', '.xml': 'Documents',
                
                # Media
                '.jpg': 'Media', '.jpeg': 'Media', '.png': 'Media', '.gif': 'Media', 
                '.mp3': 'Media', '.mp4': 'Media', '.avi': 'Media', '.mov': 'Media',
                '.wav': 'Media', '.flac': 'Media', '.mkv': 'Media', '.webm': 'Media',
                '.webp': 'Media', '.bmp': 'Media', '.tiff': 'Media', '.svg': 'Media',
                
                # Archives
                '.zip': 'Archives', '.rar': 'Archives', '.7z': 'Archives', '.tar': 'Archives',
                '.gz': 'Archives', '.bz2': 'Archives', '.iso': 'Archives', '.cab': 'Archives',
                
                # System
                '.sys': 'System', '.ini': 'System', '.log': 'System', '.tmp': 'System',
                '.reg': 'System', '.config': 'System', '.dat': 'System', '.bin': 'System'
            }
            
            # Program directories to identify installed software
            program_dirs = [
                "Program Files", "Program Files (x86)", "ProgramData", 
                "AppData", "Windows", "Users"
            ]
            
            # Scan the selected drive
            for root, dirs, files in os.walk(f"{selected_drive}\\"):
                try:
                    # Skip paths in excluded_paths
                    if any(excluded in root for excluded in self.settings.get("excluded_paths", [])):
                        dirs[:] = []  # Skip all subdirectories
                        continue
                    
                    # Process files in current directory
                    for file in files:
                        try:
                            file_path = os.path.join(root, file)
                            
                            # Get file size
                            try:
                                file_size = os.path.getsize(file_path)
                            except (OSError, FileNotFoundError):
                                file_size = 0
                            
                            # Determine category
                            extension = os.path.splitext(file)[1].lower()
                            category = extension_categories.get(extension, "Other")
                            
                            # Special case for executables to distinguish between programs and games
                            if extension == '.exe':
                                if any(game_dir in root.lower() for game_dir in [
                                    "steam", "epic games", "games", "ubisoft", "origin",
                                    "battle.net", "gog", "ea games", "minecraft"
                                ]):
                                    category = "Games"
                                else:
                                    category = "Programs"
                            
                            # Add file to appropriate category
                            self.categories[category]["size"] += file_size
                            self.categories[category]["count"] += 1
                            self.categories[category]["paths"].append({
                                "path": file_path,
                                "size": file_size,
                                "name": file
                            })
                            
                            # Update progress periodically
                            total_scanned += 1
                            if total_scanned % 100 == 0:
                                self.progress['value'] = min(100, (total_scanned / 10000) * 100)
                                self.update_idletasks()
                                
                        except Exception as e:
                            # Log individual file errors without stopping the scan
                            print(f"Error processing file {file}: {str(e)}")
                            
                except PermissionError:
                    # Skip directories we can't access
                    continue
                    
            # Update UI with results
            self.display_categories()
            self.update_stats()
            
            # Save scan timestamp
            self.settings["last_scan"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.save_settings()
            
            messagebox.showinfo("Scan Complete", 
                             f"Analyzed {total_scanned} files in {selected_drive}")
                             
        except Exception as e:
            messagebox.showerror("Error", f"Scanning error: {str(e)}")
            
    def update_stats(self):
        total_gb = round(self.total_size / (1024**3), 2)
        stats = f"Total Games: {len(self.games)} | Total Size: {total_gb} GB"
        self.stats_label.config(text=stats)
        def display_categories(self):
            # Clear existing list
            self.games_list.delete(0, tk.END)
        
            # Get selected category
            selected_category = self.category_var.get()
        
            if selected_category == "All Categories":
                # Display summary of all categories
                for category_name, category_data in self.categories.items():
                    size_gb = round(category_data["size"] / (1024**3), 2)
                    entry = f"{size_gb:6.2f} GB  |  {category_name:<20} | {category_data['count']} items"
                    self.games_list.insert(tk.END, entry)
                
                    # Style alternate rows
                    if self.games_list.size() % 2 == 0:
                        self.games_list.itemconfig(tk.END, bg='#f0f0f0')
            else:
                # Display details for selected category
                category_data = self.categories[selected_category]
            
                # Sort by size (largest first)
                sorted_items = sorted(category_data["paths"], key=lambda x: x["size"], reverse=True)
            
                for item in sorted_items:
                    size_gb = round(item["size"] / (1024**3), 2) if item["size"] > 1024**3 else round(item["size"] / (1024**2), 2)
                    size_unit = "GB" if item["size"] > 1024**3 else "MB"
                
                    parent_folder = os.path.basename(os.path.dirname(item["path"]))
                    formatted_entry = f"{size_gb:6.2f} {size_unit}  |  {item['name']:<40} | {parent_folder}"
                    self.games_list.insert(tk.END, formatted_entry)
                
                    # Style alternate rows
                    if self.games_list.size() % 2 == 0:
                        self.games_list.itemconfig(tk.END, bg='#f0f0f0')
                    
        def filter_by_category(self, event=None):
            self.display_categories()
        
            # Update category info
            selected_category = self.category_var.get()
            if selected_category != "All Categories":
                cat_data = self.categories[selected_category]
                size_gb = round(cat_data["size"] / (1024**3), 2)
                self.category_info.config(text=f"Total: {size_gb} GB, {cat_data['count']} items")
            else:
                self.category_info.config(text="")
    def delete_multiple(self):
        selections = self.games_list.curselection()
        if not selections:
            messagebox.showwarning("Warning", "Please select games to delete")
            return
            
        if messagebox.askyesno("Confirm Delete", f"Delete {len(selections)} selected games?"):
            for idx in reversed(selections):
                entry = self.games_list.get(idx)
                # Extract the full path correctly from the formatted entry
                game_name = entry.split(" | ")[1].strip()
                parent_folder = entry.split(" | ")[2].strip()
                full_path = os.path.join(parent_folder, game_name)
                
                try:
                    if os.path.exists(full_path):
                        if os.path.isfile(full_path):
                            os.remove(full_path)
                        else:
                            parent_dir = os.path.dirname(full_path)
                            if os.path.exists(parent_dir):
                                shutil.rmtree(parent_dir)
                        # Remove from games list and update total size
                        self.games.remove(full_path)
                        self.games_list.delete(idx)
                    else:
                        messagebox.showinfo("Info", f"Path no longer exists: {full_path}")
                        self.games_list.delete(idx)
                        
                except PermissionError:
                    messagebox.showwarning("Permission Denied", 
                        f"Unable to delete {full_path}\nTry running as administrator")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to delete {full_path}: {str(e)}")

            self.update_stats()
            self.games_list.selection_clear(0, tk.END)
            
    def save_settings(self):
        with open('settings.json', 'w') as f:
            json.dump(self.settings, f)

    def on_closing(self):
        self.save_settings()
        self.destroy()

if __name__ == '__main__':
    app = StorageAnalyzer()  # Changed from GameAnalyzer to StorageAnalyzer
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
    def manage_exclusions(self):
        """Add or remove paths from the exclusion list"""
        exclusion_window = tk.Toplevel(self)
        exclusion_window.title("Manage Excluded Paths")
        exclusion_window.geometry("500x400")
        
        # Create exclusion list display
        ttk.Label(exclusion_window, text="Current Excluded Paths:").pack(pady=5)
        
        exclusion_frame = ttk.Frame(exclusion_window)
        exclusion_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        exclusion_list = tk.Listbox(exclusion_frame)
        exclusion_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(exclusion_frame, command=exclusion_list.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        exclusion_list.config(yscrollcommand=scrollbar.set)
        
        # Populate the list
        for path in self.settings.get("excluded_paths", []):
            exclusion_list.insert(tk.END, path)
            
        # Control buttons
        button_frame = ttk.Frame(exclusion_window)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Add Path", 
                 command=lambda: self.add_exclusion(exclusion_list)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Remove Selected", 
                 command=lambda: self.remove_exclusion(exclusion_list)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", 
                 command=exclusion_window.destroy).pack(side=tk.RIGHT, padx=5)
        
    def add_exclusion(self, exclusion_list):
        path = filedialog.askdirectory(title="Select Directory to Exclude")
        if path:
            if path not in self.settings.get("excluded_paths", []):
                if "excluded_paths" not in self.settings:
                    self.settings["excluded_paths"] = []
                self.settings["excluded_paths"].append(path)
                exclusion_list.insert(tk.END, path)
                self.save_settings()
                
    def remove_exclusion(self, exclusion_list):
        selection = exclusion_list.curselection()
        if selection:
            path = exclusion_list.get(selection[0])
            self.settings["excluded_paths"].remove(path)
            exclusion_list.delete(selection[0])
            self.save_settings()