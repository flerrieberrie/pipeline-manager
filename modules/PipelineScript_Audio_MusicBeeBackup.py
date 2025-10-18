#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PipelineScript_MusicBeeBackup.py
Description: Backs up MusicBee library to OneDrive, only transferring changed or new files
Author: Florian Dheer
"""

import os
import sys
import time
import datetime
import shutil
import logging
import argparse
import hashlib
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import json

# Default paths
DEFAULT_SOURCE_DIR = "M:\\"
DEFAULT_DEST_DIR = os.path.join(os.path.expanduser("~"), "OneDrive", "_Music")

# Setup logging
def setup_logging():
    """Configure logging for the script."""
    log_dir = os.path.join(os.path.expanduser("~"), "AppData", "Local", "PipelineManager", "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"musicbee_backup_{timestamp}.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    return logging.getLogger("MusicBeeBackup")

logger = setup_logging()

class FileHashDatabase:
    """Manages a database of file hashes to track changes."""
    
    def __init__(self, db_path=None):
        """Initialize the hash database."""
        if db_path is None:
            # Use default location in AppData
            db_dir = os.path.join(os.path.expanduser("~"), "AppData", "Local", "PipelineManager")
            os.makedirs(db_dir, exist_ok=True)
            db_path = os.path.join(db_dir, "musicbee_file_hashes.json")
        
        self.db_path = db_path
        self.hashes = self._load_db()
    
    def _load_db(self):
        """Load the hash database from file."""
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading hash database: {e}")
                return {}
        return {}
    
    def save_db(self):
        """Save the hash database to file."""
        try:
            with open(self.db_path, 'w', encoding='utf-8') as f:
                json.dump(self.hashes, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Error saving hash database: {e}")
            return False
    
    def get_hash(self, file_path):
        """Get stored hash for a file if available."""
        rel_path = os.path.normpath(file_path).lower()
        return self.hashes.get(rel_path)
    
    def update_hash(self, file_path, new_hash):
        """Update hash for a file."""
        rel_path = os.path.normpath(file_path).lower()
        self.hashes[rel_path] = new_hash
    
    def remove_hash(self, file_path):
        """Remove hash for a file that no longer exists."""
        rel_path = os.path.normpath(file_path).lower()
        if rel_path in self.hashes:
            del self.hashes[rel_path]
    
    def clean_missing_files(self, existing_files):
        """Remove hashes for files that no longer exist."""
        existing_paths = {os.path.normpath(path).lower() for path in existing_files}
        to_remove = []
        
        for path in self.hashes:
            if path not in existing_paths:
                to_remove.append(path)
        
        for path in to_remove:
            del self.hashes[path]
        
        return len(to_remove)


class MusicBeeBackupUI:
    """GUI for MusicBee backup utility."""
    
    def __init__(self, root):
        """Initialize the UI."""
        self.root = root
        self.root.title("MusicBee to OneDrive Backup")
        self.root.geometry("750x700")
        self.root.minsize(750, 600)
        
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)
        
        # Create a styled frame for the header
        header_frame = tk.Frame(self.root, bg="#2c3e50", height=60)
        header_frame.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        header_frame.grid_propagate(False)
        
        # Title in header
        title_label = tk.Label(header_frame, text="MusicBee to OneDrive Backup", 
                             font=("Arial", 16, "bold"), fg="white", bg="#2c3e50")
        title_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        # Main content frame
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # Configuration Frame
        self.create_config_frame(main_frame)
        
        # Results Frame
        self.create_results_frame(main_frame)
        
        # Status Bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        self.status_bar = tk.Label(self.root, textvariable=self.status_var, bd=1, 
                                 relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.grid(row=2, column=0, sticky="ew")
        
        # Initialize variables
        self.syncing = False
        self.hash_db = FileHashDatabase()
        
        # Initialize paths
        self.source_dir_var.set(DEFAULT_SOURCE_DIR)
        self.dest_dir_var.set(DEFAULT_DEST_DIR)
        
        # Set up the close event handler
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def is_onedrive_cloud_only(self, file_path):
        """Check if a file is OneDrive cloud-only (not downloaded locally)."""
        try:
            # Check for specific OneDrive attributes
            if sys.platform == "win32":
                import ctypes
                from ctypes import windll, wintypes
                
                FILE_ATTRIBUTE_PINNED = 0x00080000  # FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS
                FILE_ATTRIBUTE_UNPINNED = 0x00100000  # FILE_ATTRIBUTE_RECALL_ON_OPEN
                
                attrs = windll.kernel32.GetFileAttributesW(file_path)
                if attrs != 0xFFFFFFFF:  # INVALID_FILE_ATTRIBUTES
                    # If file has OneDrive placeholder attributes
                    return bool(attrs & (FILE_ATTRIBUTE_PINNED | FILE_ATTRIBUTE_UNPINNED))
            
            # Fallback: check by looking at the file size on disk vs actual size
            # Cloud files typically have a very small size on disk until downloaded
            if os.path.exists(file_path):
                import stat
                try:
                    # This is a simplistic approach - OneDrive placeholders are typically small
                    st = os.stat(file_path)
                    if hasattr(st, 'st_size') and hasattr(st, 'st_blocks'):
                        real_size = st.st_size
                        disk_size = st.st_blocks * 512  # st_blocks is in 512-byte units
                        return disk_size < real_size / 10  # If disk size is < 10% of reported size
                except:
                    pass
                    
            return False
        except Exception as e:
            logger.debug(f"Error checking OneDrive status for {file_path}: {e}")
            return False
        
    def on_closing(self):
        """Handle the closing event."""
        if self.syncing:
            if messagebox.askokcancel("Quit", "A backup operation is in progress. Are you sure you want to quit?"):
                self.root.destroy()
        else:
            # Save hash database before closing
            if hasattr(self, 'hash_db'):
                self.hash_db.save_db()
            self.root.destroy()
    
    def create_config_frame(self, parent):
        """Create the configuration frame."""
        config_frame = ttk.LabelFrame(parent, text="Backup Configuration")
        config_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        config_frame.columnconfigure(1, weight=1)
        
        # Source directory
        ttk.Label(config_frame, text="MusicBee Library:").grid(row=0, column=0, sticky="w", padx=10, pady=10)
        self.source_dir_var = tk.StringVar()
        ttk.Entry(config_frame, textvariable=self.source_dir_var, width=50).grid(row=0, column=1, sticky="ew", padx=5, pady=10)
        ttk.Button(config_frame, text="Browse", command=lambda: self.browse_directory(self.source_dir_var, "Select MusicBee Library")).grid(row=0, column=2, padx=5, pady=10)
        
        # Destination directory
        ttk.Label(config_frame, text="OneDrive Destination:").grid(row=1, column=0, sticky="w", padx=10, pady=10)
        self.dest_dir_var = tk.StringVar()
        ttk.Entry(config_frame, textvariable=self.dest_dir_var, width=50).grid(row=1, column=1, sticky="ew", padx=5, pady=10)
        ttk.Button(config_frame, text="Browse", command=lambda: self.browse_directory(self.dest_dir_var, "Select OneDrive Destination")).grid(row=1, column=2, padx=5, pady=10)
        
        # Options
        options_frame = ttk.LabelFrame(config_frame, text="Options")
        options_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=10, pady=10)
        
        self.verify_hashes_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Verify file integrity with hash comparison (slower but more accurate)", 
                      variable=self.verify_hashes_var).grid(row=0, column=0, sticky="w", padx=10, pady=5)
        
        self.skip_existing_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Skip copying files that already exist with same size/date", 
                      variable=self.skip_existing_var).grid(row=1, column=0, sticky="w", padx=10, pady=5)
        
        self.cloud_aware_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="OneDrive cloud-aware mode (avoid downloading cloud-only files)", 
                      variable=self.cloud_aware_var).grid(row=2, column=0, sticky="w", padx=10, pady=5)
        
        self.delete_orphaned_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Delete files in destination that don't exist in source (CAUTION)", 
                      variable=self.delete_orphaned_var).grid(row=3, column=0, sticky="w", padx=10, pady=5)
        
        # Buttons
        btn_frame = ttk.Frame(config_frame)
        btn_frame.grid(row=3, column=0, columnspan=3, sticky="ew", pady=10)
        btn_frame.columnconfigure(1, weight=1)
        
        self.analyze_btn = ttk.Button(btn_frame, text="Analyze Libraries", command=self.analyze_libraries, width=15)
        self.analyze_btn.grid(row=0, column=0, padx=10)
        
        self.backup_btn = ttk.Button(btn_frame, text="Start Backup", command=self.start_backup, width=15)
        self.backup_btn.grid(row=0, column=2, padx=10)
    
    def create_results_frame(self, parent):
        """Create the results display frame."""
        results_frame = ttk.LabelFrame(parent, text="Backup Progress and Results")
        results_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        
        self.results_notebook = ttk.Notebook(results_frame)
        self.results_notebook.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Analysis tab
        self.analysis_frame = ttk.Frame(self.results_notebook)
        self.results_notebook.add(self.analysis_frame, text="Library Analysis")
        self.analysis_frame.columnconfigure(0, weight=1)
        self.analysis_frame.rowconfigure(0, weight=1)
        
        self.analysis_text = tk.Text(self.analysis_frame, wrap=tk.WORD)
        self.analysis_text.grid(row=0, column=0, sticky="nsew")
        
        analysis_scrollbar = ttk.Scrollbar(self.analysis_frame, command=self.analysis_text.yview)
        analysis_scrollbar.grid(row=0, column=1, sticky="ns")
        self.analysis_text.config(yscrollcommand=analysis_scrollbar.set)
        
        # Backup tab
        self.backup_frame = ttk.Frame(self.results_notebook)
        self.results_notebook.add(self.backup_frame, text="Backup Progress")
        self.backup_frame.columnconfigure(0, weight=1)
        self.backup_frame.rowconfigure(0, weight=1)
        
        self.backup_text = tk.Text(self.backup_frame, wrap=tk.WORD)
        self.backup_text.grid(row=0, column=0, sticky="nsew")
        
        backup_scrollbar = ttk.Scrollbar(self.backup_frame, command=self.backup_text.yview)
        backup_scrollbar.grid(row=0, column=1, sticky="ns")
        self.backup_text.config(yscrollcommand=backup_scrollbar.set)
        
        # Summary tab
        self.summary_frame = ttk.Frame(self.results_notebook)
        self.results_notebook.add(self.summary_frame, text="Backup Summary")
        self.summary_frame.columnconfigure(0, weight=1)
        self.summary_frame.rowconfigure(0, weight=1)
        
        self.summary_text = tk.Text(self.summary_frame, wrap=tk.WORD)
        self.summary_text.grid(row=0, column=0, sticky="nsew")
        
        summary_scrollbar = ttk.Scrollbar(self.summary_frame, command=self.summary_text.yview)
        summary_scrollbar.grid(row=0, column=1, sticky="ns")
        self.summary_text.config(yscrollcommand=summary_scrollbar.set)
    
    def browse_directory(self, string_var, title):
        """Browse for a directory and update the StringVar."""
        directory = filedialog.askdirectory(title=title)
        if directory:
            string_var.set(directory)
    
    def append_to_text_widget(self, text_widget, message):
        """Append message to a text widget."""
        def update_text():
            text_widget.insert(tk.END, message)
            text_widget.see(tk.END)
            text_widget.update_idletasks()
        self.root.after(0, update_text)
    
    def calculate_file_hash(self, file_path, buffer_size=65536):
        """Calculate MD5 hash of a file."""
        try:
            md5 = hashlib.md5()
            with open(file_path, 'rb') as f:
                while True:
                    data = f.read(buffer_size)
                    if not data:
                        break
                    md5.update(data)
            return md5.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating hash for {file_path}: {e}")
            return None
    
    def analyze_libraries(self):
        """Analyze source and destination libraries."""
        source_dir = self.source_dir_var.get()
        dest_dir = self.dest_dir_var.get()
        
        if not source_dir or not os.path.exists(source_dir):
            messagebox.showerror("Error", "Source directory does not exist!")
            return
        
        if not dest_dir:
            messagebox.showerror("Error", "Please specify a destination directory!")
            return
        
        # Create destination if it doesn't exist
        if not os.path.exists(dest_dir):
            try:
                os.makedirs(dest_dir)
                self.append_to_text_widget(self.analysis_text, f"Created destination directory: {dest_dir}\n")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create destination directory: {e}")
                return
        
        # Disable buttons
        self.analyze_btn.config(state=tk.DISABLED)
        self.backup_btn.config(state=tk.DISABLED)
        self.syncing = True
        
        # Clear text widgets
        self.analysis_text.delete(1.0, tk.END)
        self.backup_text.delete(1.0, tk.END)
        self.summary_text.delete(1.0, tk.END)
        
        # Start analysis thread
        threading.Thread(target=self.analyze_process, daemon=True).start()
    
    def should_exclude_directory(self, dir_path):
        """Check if directory should be excluded from scanning."""
        dir_name = os.path.basename(dir_path).lower()
        parent_dir = os.path.basename(os.path.dirname(dir_path)).lower()
        
        # Exclude system directories and Recycle Bin
        excluded_dirs = [
            '$recycle.bin',    # Windows Recycle Bin (lowercase for comparison)
            'system volume information',
            'recycled',         # Older Windows recycling
            'recycler',         # Older Windows recycling
            '$windows.~bt',     # Windows update temp files
            '$windows.~ws',     # Windows update temp files
            'windows.old',      # Old Windows installation
            'hiberfil.sys',     # Hibernation file
            'pagefile.sys',     # Page file
            'swapfile.sys',     # Swap file
            'thumbs.db',        # Thumbnail cache
            'desktop.ini',      # Folder settings
            '.trashes',         # macOS trash
            '.trash-1000',      # Linux trash
            '.dropbox.cache',   # Dropbox cache
            'onedrive.tmp',     # OneDrive temporary
            '.tmp',             # Generic temp dirs
            '.temp',            # Generic temp dirs
            'temp',             # Generic temp dirs
            'tmp',              # Generic temp dirs
            '.synologyworkingdirectory'  # Synology NAS working directory
        ]
        
        # Check if it's a hidden directory (starts with dot)
        if dir_name.startswith('.'):
            return True
            
        # Check for recycle bin and system directories
        if dir_name.lower() in excluded_dirs:
            return True
            
        # Check for full path patterns (case insensitive)
        if '$recycle.bin' in dir_path.lower() or '$RECYCLE.BIN' in dir_path:
            return True
            
        # Check for OneDrive version history folders
        if dir_name == 'versions' and parent_dir == 'onedrive':
            return True
        
        # Check for Synology working directory (case insensitive check)
        if '.synologyworkingdirectory' in dir_path.lower():
            return True
            
        return False

    def analyze_process(self):
        """Background process to analyze libraries."""
        try:
            source_dir = self.source_dir_var.get()
            dest_dir = self.dest_dir_var.get()
            verify_hashes = self.verify_hashes_var.get()
            cloud_aware = self.cloud_aware_var.get()
            
            # Detect if we're using OneDrive
            is_onedrive = "onedrive" in dest_dir.lower() and cloud_aware
            if is_onedrive:
                self.append_to_text_widget(self.analysis_text, "OneDrive destination detected - using cloud-aware scanning\n")
            
            start_time = time.time()
            
            self.status_var.set("Analyzing libraries...")
            self.append_to_text_widget(self.analysis_text, "===== ANALYZING MUSICBEE LIBRARY =====\n")
            self.results_notebook.select(0)
            
            # Get source files
            self.append_to_text_widget(self.analysis_text, f"Scanning source directory: {source_dir}\n")
            source_files = []
            source_file_count = 0
            total_source_size = 0
            excluded_dirs_count = 0
            
            for root, dirs, files in os.walk(source_dir):
                # Filter out system directories like Recycle Bin
                dirs[:] = [d for d in dirs if not self.should_exclude_directory(os.path.join(root, d))]
                
                for file in files:
                    source_file_count += 1
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, source_dir)
                    
                    # Skip temporary files and system files
                    if (file.lower().endswith(('.tmp', '.temp', '.ini', '.lnk', '.db')) or 
                        file.startswith('~') or 
                        file.lower() in ['thumbs.db', 'desktop.ini']):
                        continue
                    
                    try:
                        file_size = os.path.getsize(file_path)
                        total_source_size += file_size
                        mtime = os.path.getmtime(file_path)
                        
                        source_files.append({
                            'path': file_path,
                            'rel_path': rel_path,
                            'size': file_size,
                            'mtime': mtime
                        })
                    except (FileNotFoundError, PermissionError) as e:
                        self.append_to_text_widget(
                            self.analysis_text,
                            f"Warning: Cannot access {rel_path}: {e}\n"
                        )
                    
                    if source_file_count % 100 == 0:
                        self.status_var.set(f"Scanning source: {source_file_count} files found...")
            
            self.append_to_text_widget(
                self.analysis_text, 
                f"Found {len(source_files)} files in source ({self.format_size(total_source_size)})\n"
            )
            
            # Get destination files with OneDrive awareness
            self.append_to_text_widget(self.analysis_text, f"Scanning destination directory: {dest_dir}\n")
            dest_files = []
            dest_file_count = 0
            total_dest_size = 0
            cloud_only_count = 0
            
            for root, dirs, files in os.walk(dest_dir):
                # Filter out system directories like Recycle Bin
                dirs[:] = [d for d in dirs if not self.should_exclude_directory(os.path.join(root, d))]
                
                for file in files:
                    dest_file_count += 1
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, dest_dir)
                    
                    # Skip temporary files and system files
                    if (file.lower().endswith(('.tmp', '.temp', '.ini', '.lnk', '.db')) or 
                        file.startswith('~') or 
                        file.lower() in ['thumbs.db', 'desktop.ini']):
                        continue
                    
                    try:
                        # Check if this is a cloud-only file
                        is_cloud_only = is_onedrive and self.is_onedrive_cloud_only(file_path)
                        if is_cloud_only:
                            cloud_only_count += 1
                            
                        # Get file metadata (carefully to avoid triggering downloads)
                        try:
                            file_size = os.path.getsize(file_path)
                            mtime = os.path.getmtime(file_path)
                        except Exception as e:
                            self.append_to_text_widget(
                                self.analysis_text,
                                f"Warning: Error getting metadata for {rel_path}: {e}\n"
                            )
                            continue
                            
                        total_dest_size += file_size
                        
                        dest_files.append({
                            'path': file_path,
                            'rel_path': rel_path,
                            'size': file_size,
                            'mtime': mtime,
                            'is_cloud_only': is_cloud_only
                        })
                    except (FileNotFoundError, PermissionError) as e:
                        self.append_to_text_widget(
                            self.analysis_text,
                            f"Warning: Cannot access {rel_path}: {e}\n"
                        )
                    
                    if dest_file_count % 100 == 0:
                        self.status_var.set(f"Scanning destination: {dest_file_count} files found...")
            
            if is_onedrive and cloud_only_count > 0:
                self.append_to_text_widget(
                    self.analysis_text, 
                    f"Found {cloud_only_count} cloud-only files (will avoid downloading for comparison)\n"
                )
                
            self.append_to_text_widget(
                self.analysis_text, 
                f"Found {len(dest_files)} files in destination ({self.format_size(total_dest_size)})\n"
            )
            
            # Find files that need to be copied (new or updated)
            self.append_to_text_widget(self.analysis_text, "Analyzing differences between libraries...\n")
            
            # Build lookup dictionaries
            dest_lookup = {file['rel_path'].lower(): file for file in dest_files}
            
            files_to_copy = []
            files_to_skip = []
            orphaned_files = []
            total_copy_size = 0
            
            # First, find all the files that need to be copied
            for source_file in source_files:
                rel_path = source_file['rel_path']
                source_path = source_file['path']
                source_size = source_file['size']
                source_mtime = source_file['mtime']
                
                # Check if file exists in destination
                if rel_path.lower() in dest_lookup:
                    dest_file = dest_lookup[rel_path.lower()]
                    dest_path = dest_file['path']
                    dest_size = dest_file['size']
                    dest_mtime = dest_file['mtime']
                    is_cloud_only = dest_file.get('is_cloud_only', False)
                    
                    # If the file is already cloud-only in OneDrive, skip it
                    # No need to re-copy files that are already in OneDrive
                    if is_cloud_only:
                        files_to_skip.append(source_file)
                        continue
                    
                    # Check if file needs updating
                    needs_update = False
                    
                    # Size or mtime difference
                    if source_size != dest_size or abs(source_mtime - dest_mtime) > 2:
                        needs_update = True
                    
                    # For cloud-only files, we should avoid hash verification if possible
                    should_verify_hash = verify_hashes and source_size == dest_size and not needs_update
                    
                    if should_verify_hash:
                        # If we're dealing with a cloud-only file, try to avoid downloading
                        if is_cloud_only:
                            # First check if we have stored hashes to avoid triggering a download
                            source_stored_hash = self.hash_db.get_hash(source_path)
                            dest_stored_hash = self.hash_db.get_hash(dest_path)
                            
                            if source_stored_hash and dest_stored_hash:
                                if source_stored_hash != dest_stored_hash:
                                    needs_update = True
                                # We have hashes and they match - skip further checking
                                should_verify_hash = False
                            else:
                                # We don't have stored hashes - try to get the source hash
                                # but skip the destination hash to avoid download
                                source_hash = self.calculate_file_hash(source_path)
                                if source_hash:
                                    self.hash_db.update_hash(source_path, source_hash)
                                
                                # Instead of checking the hash now, we'll just copy the file
                                # This ensures we don't trigger downloads unnecessarily
                                self.append_to_text_widget(
                                    self.analysis_text,
                                    f"Cloud-only file without hash: {rel_path} - will update\n"
                                )
                                needs_update = True
                                should_verify_hash = False
                        
                        # For regular files, do standard hash verification
                        if should_verify_hash:
                            self.status_var.set(f"Verifying hash for {rel_path}")
                            
                            # Get stored hashes if available
                            source_stored_hash = self.hash_db.get_hash(source_path)
                            dest_stored_hash = self.hash_db.get_hash(dest_path)
                            
                            if source_stored_hash and dest_stored_hash:
                                if source_stored_hash != dest_stored_hash:
                                    needs_update = True
                            else:
                                # Calculate hashes
                                source_hash = self.calculate_file_hash(source_path)
                                dest_hash = self.calculate_file_hash(dest_path)
                                
                                # Update hash database
                                if source_hash:
                                    self.hash_db.update_hash(source_path, source_hash)
                                if dest_hash:
                                    self.hash_db.update_hash(dest_path, dest_hash)
                                
                                if source_hash and dest_hash and source_hash != dest_hash:
                                    needs_update = True
                    
                    if needs_update:
                        files_to_copy.append(source_file)
                        total_copy_size += source_size
                    else:
                        files_to_skip.append(source_file)
                else:
                    # New file
                    files_to_copy.append(source_file)
                    total_copy_size += source_size
            
            # Find orphaned files (in destination but not in source)
            for dest_file in dest_files:
                rel_path = dest_file['rel_path']
                if not any(sf['rel_path'].lower() == rel_path.lower() for sf in source_files):
                    orphaned_files.append(dest_file)
            
            # Save the hash database
            self.hash_db.save_db()
            
            # Results summary
            analysis_time = time.time() - start_time
            self.append_to_text_widget(self.analysis_text, f"\n===== ANALYSIS SUMMARY =====\n")
            self.append_to_text_widget(self.analysis_text, f"Analysis completed in {analysis_time:.2f} seconds\n")
            self.append_to_text_widget(self.analysis_text, f"Files to copy: {len(files_to_copy)} ({self.format_size(total_copy_size)})\n")
            self.append_to_text_widget(self.analysis_text, f"Files to skip: {len(files_to_skip)} ({self.format_size(sum(f['size'] for f in files_to_skip))})\n")
            
            # Show orphaned files summary and sample
            orphaned_size = sum(f['size'] for f in orphaned_files)
            self.append_to_text_widget(self.analysis_text, 
                f"Orphaned files: {len(orphaned_files)} ({self.format_size(orphaned_size)})\n")
            
            if self.delete_orphaned_var.get() and orphaned_files:
                self.append_to_text_widget(self.analysis_text, 
                    f"\n⚠️ ATTENTION: {len(orphaned_files)} files will be DELETED from destination!\n")
                
                # Show sample of files that would be deleted (max 10)
                sample_size = min(10, len(orphaned_files))
                self.append_to_text_widget(self.analysis_text, f"\nSample of files to be deleted:\n")
                for i, file in enumerate(sorted(orphaned_files, key=lambda f: f['size'], reverse=True)[:sample_size]):
                    self.append_to_text_widget(self.analysis_text, 
                        f"{i+1}. {file['rel_path']} ({self.format_size(file['size'])})\n")
                
                # If more than 10 files would be deleted, indicate there are more
                if len(orphaned_files) > 10:
                    self.append_to_text_widget(self.analysis_text, 
                        f"... and {len(orphaned_files) - 10} more files\n")
            
            # Store results for backup process
            self.analysis_results = {
                'source_dir': source_dir,
                'dest_dir': dest_dir,
                'files_to_copy': files_to_copy,
                'files_to_skip': files_to_skip,
                'orphaned_files': orphaned_files,
                'total_copy_size': total_copy_size
            }
            
            self.status_var.set(f"Analysis complete: {len(files_to_copy)} files need copying")
            
            # Enable backup button if files need to be copied or deleted
            if files_to_copy or (self.delete_orphaned_var.get() and orphaned_files):
                self.root.after(0, lambda: self.backup_btn.config(state=tk.NORMAL))
                
            # Always re-enable analyze button
            self.root.after(0, lambda: self.analyze_btn.config(state=tk.NORMAL))
            
        except Exception as e:
            error_msg = f"Error during analysis: {str(e)}"
            logger.error(error_msg)
            self.append_to_text_widget(self.analysis_text, f"\n{error_msg}\n")
            self.status_var.set("Error during analysis")
            self.root.after(0, lambda: messagebox.showerror("Analysis Error", error_msg))
            self.root.after(0, lambda: self.analyze_btn.config(state=tk.NORMAL))
        
        finally:
            self.syncing = False
    
    def start_backup(self):
        """Start the backup process."""
        if not hasattr(self, 'analysis_results'):
            messagebox.showerror("Error", "Please analyze libraries first!")
            return
        
        # If files will be deleted, confirm with the user
        if self.delete_orphaned_var.get() and self.analysis_results['orphaned_files']:
            orphaned_count = len(self.analysis_results['orphaned_files'])
            orphaned_size = sum(f['size'] for f in self.analysis_results['orphaned_files'])
            
            confirm = messagebox.askokcancel(
                "Confirm Deletion",
                f"This will delete {orphaned_count} files ({self.format_size(orphaned_size)}) from the destination.\n\n"
                "Are you sure you want to continue?",
                icon=messagebox.WARNING
            )
            
            if not confirm:
                return
        
        # Disable buttons
        self.analyze_btn.config(state=tk.DISABLED)
        self.backup_btn.config(state=tk.DISABLED)
        self.syncing = True
        
        # Clear backup and summary text
        self.backup_text.delete(1.0, tk.END)
        self.summary_text.delete(1.0, tk.END)
        
        # Start backup thread
        threading.Thread(target=self.backup_process, daemon=True).start()
    
    def backup_process(self):
        """Background process to perform the backup."""
        try:
            results = self.analysis_results
            source_dir = results['source_dir']
            dest_dir = results['dest_dir']
            files_to_copy = results['files_to_copy']
            orphaned_files = results['orphaned_files']
            total_copy_size = results['total_copy_size']
            delete_orphaned = self.delete_orphaned_var.get()
            
            start_time = time.time()
            
            self.status_var.set("Starting backup...")
            self.append_to_text_widget(self.backup_text, "===== PERFORMING BACKUP =====\n")
            self.results_notebook.select(1)
            
            # Initialize counters
            successful_copies = 0
            failed_copies = 0
            deleted_files = 0
            failed_deletes = 0
            bytes_copied = 0
            
            # Copy files
            if files_to_copy:
                total_files = len(files_to_copy)
                
                self.append_to_text_widget(
                    self.backup_text, 
                    f"Copying {total_files} files ({self.format_size(total_copy_size)})...\n"
                )
                
                for i, file in enumerate(files_to_copy):
                    source_path = file['path']
                    rel_path = file['rel_path']
                    size = file['size']
                    
                    dest_path = os.path.join(dest_dir, rel_path)
                    dest_dir_path = os.path.dirname(dest_path)
                    
                    # Create destination directory if it doesn't exist
                    if not os.path.exists(dest_dir_path):
                        try:
                            os.makedirs(dest_dir_path)
                        except Exception as e:
                            self.append_to_text_widget(
                                self.backup_text, 
                                f"✗ Failed to create directory {dest_dir_path}: {e}\n"
                            )
                            failed_copies += 1
                            continue
                    
                    # Update progress
                    progress = (i + 1) / total_files * 100
                    self.status_var.set(f"Copying files: {i+1}/{total_files} ({progress:.1f}%)")
                    
                    # Log every 10 files or if it's a larger file
                    if i % 10 == 0 or size > 10 * 1024 * 1024:  # Log every 10 files or files over 10MB
                        self.append_to_text_widget(
                            self.backup_text,
                            f"Copying ({i+1}/{total_files}): {rel_path} ({self.format_size(size)})\n"
                        )
                    
                    try:
                        # Ensure destination directory exists
                        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                        
                        # Copy the file
                        shutil.copy2(source_path, dest_path)
                        
                        # Update counters
                        successful_copies += 1
                        bytes_copied += size
                        
                        # Calculate hash for the copied file if hash verification is enabled
                        if self.verify_hashes_var.get():
                            # Store hash of source file if not already done
                            if not self.hash_db.get_hash(source_path):
                                source_hash = self.calculate_file_hash(source_path)
                                if source_hash:
                                    self.hash_db.update_hash(source_path, source_hash)
                            
                            # Store hash of destination file
                            dest_hash = self.calculate_file_hash(dest_path)
                            if dest_hash:
                                self.hash_db.update_hash(dest_path, dest_hash)
                        
                    except Exception as e:
                        self.append_to_text_widget(
                            self.backup_text, 
                            f"✗ Failed to copy {rel_path}: {e}\n"
                        )
                        failed_copies += 1
            else:
                self.append_to_text_widget(self.backup_text, "No files need to be copied.\n")
            
            # Delete orphaned files if requested
            if delete_orphaned and orphaned_files:
                self.append_to_text_widget(
                    self.backup_text, 
                    f"\nDeleting {len(orphaned_files)} orphaned files...\n"
                )
                
                for file in orphaned_files:
                    dest_path = file['path']
                    rel_path = file['rel_path']
                    
                    try:
                        os.remove(dest_path)
                        deleted_files += 1
                        self.append_to_text_widget(
                            self.backup_text, 
                            f"Deleted: {rel_path}\n"
                        )
                        
                        # Remove hash from database
                        self.hash_db.remove_hash(dest_path)
                        
                    except Exception as e:
                        self.append_to_text_widget(
                            self.backup_text, 
                            f"✗ Failed to delete {rel_path}: {e}\n"
                        )
                        failed_deletes += 1
            
            # Clean up empty directories in destination
            if delete_orphaned:
                self.append_to_text_widget(self.backup_text, "\nCleaning up empty directories...\n")
                empty_dirs_removed = 0
                
                for root, dirs, files in os.walk(dest_dir, topdown=False):
                    if not os.listdir(root) and root != dest_dir:
                        try:
                            os.rmdir(root)
                            empty_dirs_removed += 1
                        except:
                            pass
                
                self.append_to_text_widget(
                    self.backup_text, 
                    f"Removed {empty_dirs_removed} empty directories\n"
                )
            
            # Save hash database
            self.hash_db.save_db()
            
            # Calculate timing
            backup_time = time.time() - start_time
            backup_speed = bytes_copied / backup_time if backup_time > 0 else 0
            
            # Update summary
            self.append_to_text_widget(self.summary_text, "===== BACKUP SUMMARY =====\n")
            self.append_to_text_widget(self.summary_text, f"Backup completed in {backup_time:.2f} seconds\n")
            self.append_to_text_widget(self.summary_text, f"Files successfully copied: {successful_copies}\n")
            self.append_to_text_widget(self.summary_text, f"Total data copied: {self.format_size(bytes_copied)}\n")
            self.append_to_text_widget(self.summary_text, f"Average speed: {self.format_size(backup_speed)}/s\n")
            
            if failed_copies > 0:
                self.append_to_text_widget(self.summary_text, f"Failed copies: {failed_copies}\n")
            
            if delete_orphaned:
                self.append_to_text_widget(self.summary_text, f"Orphaned files deleted: {deleted_files}\n")
                if failed_deletes > 0:
                    self.append_to_text_widget(self.summary_text, f"Failed deletions: {failed_deletes}\n")
            
            # Final status
            if failed_copies == 0 and failed_deletes == 0:
                self.status_var.set(f"Backup completed successfully: {successful_copies} files copied")
                self.append_to_text_widget(
                    self.summary_text, 
                    "\n✓ Backup completed successfully!\n"
                )
                self.results_notebook.select(2)
                
                self.root.after(0, lambda: messagebox.showinfo(
                    "Backup Complete", 
                    f"MusicBee backup completed successfully!\n\n"
                    f"• {successful_copies} files copied ({self.format_size(bytes_copied)})\n"
                    f"• {deleted_files} orphaned files removed\n"
                    f"• Completed in {backup_time:.1f} seconds"
                ))
            else:
                error_count = failed_copies + failed_deletes
                self.status_var.set(f"Backup completed with {error_count} errors")
                self.append_to_text_widget(
                    self.summary_text, 
                    f"\n⚠ Backup completed with {error_count} errors.\n"
                )
                self.results_notebook.select(2)
                
                self.root.after(0, lambda: messagebox.showwarning(
                    "Backup Completed with Errors", 
                    f"MusicBee backup completed with {error_count} errors.\n\n"
                    f"• {successful_copies} files copied successfully\n"
                    f"• {failed_copies} files failed to copy\n"
                    f"• {deleted_files} orphaned files removed\n"
                    f"• {failed_deletes} files failed to delete\n\n"
                    f"Check the Backup Progress tab for details."
                ))
            
        except Exception as e:
            error_msg = f"Error during backup: {str(e)}"
            logger.error(error_msg)
            self.append_to_text_widget(self.backup_text, f"\n{error_msg}\n")
            self.status_var.set("Error during backup")
            self.root.after(0, lambda: messagebox.showerror("Backup Error", error_msg))
        
        finally:
            # Re-enable buttons
            self.root.after(0, lambda: self.analyze_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.backup_btn.config(state=tk.NORMAL))
            self.syncing = False
    
    @staticmethod
    def format_size(size_bytes):
        """Format file size from bytes to human-readable format."""
        if size_bytes < 1024:
            return f"{size_bytes} bytes"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes/1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes/(1024*1024):.1f} MB"
        else:
            return f"{size_bytes/(1024*1024*1024):.2f} GB"


def main():
    """Main function for standalone execution."""
    if len(sys.argv) > 1:
        # Command-line mode
        parser = argparse.ArgumentParser(description="MusicBee to OneDrive Backup Tool")
        parser.add_argument("--source", default=DEFAULT_SOURCE_DIR, help="Source MusicBee library path")
        parser.add_argument("--dest", default=DEFAULT_DEST_DIR, help="Destination OneDrive path")
        parser.add_argument("--verify-hashes", action="store_true", help="Verify file integrity with hashes")
        parser.add_argument("--skip-existing", action="store_true", help="Skip existing files with same size/date")
        parser.add_argument("--delete-orphaned", action="store_true", help="Delete orphaned files in destination")
        parser.add_argument("--auto-run", action="store_true", help="Run without confirmation")
        
        args = parser.parse_args()
        
        # TODO: Implement command-line operation
        print("Command-line mode not fully implemented yet.")
        print(f"Would backup from {args.source} to {args.dest}")
        return 0
    else:
        # GUI mode
        root = tk.Tk()
        app = MusicBeeBackupUI(root)
        root.mainloop()
        return 0

if __name__ == "__main__":
    sys.exit(main())