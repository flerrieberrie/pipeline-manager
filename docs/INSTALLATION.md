# Installation Guide

## Prerequisites

### Python Installation

1. **Download Python 3.8 or higher** from [python.org](https://www.python.org/downloads/)
2. During installation, **check "Add Python to PATH"**
3. Verify installation:
   ```bash
   python --version
   ```

### System-Specific Requirements

#### Windows
- No additional requirements for basic functionality
- For pyexiv2: May require Visual C++ Redistributable

#### macOS
- Xcode Command Line Tools may be required:
  ```bash
  xcode-select --install
  ```

#### Linux (Ubuntu/Debian)
- Install required system libraries:
  ```bash
  sudo apt-get update
  sudo apt-get install python3-tk python3-pip libexiv2-dev
  ```

## Installation Methods

### Method 1: Automatic Installation (Recommended)

1. **Navigate to the project directory**
   ```bash
   cd /path/to/floriandheer
   ```

2. **Run the installer**
   ```bash
   python install_dependencies.py
   ```

3. **Follow the prompts** - The installer will:
   - Check for existing packages
   - Show which dependencies are missing
   - Ask for confirmation before installing
   - Provide installation status for each package

### Method 2: Manual Installation

1. **Using pip with requirements.txt**
   ```bash
   pip install -r requirements.txt
   ```

2. **Install packages individually** (if needed)
   ```bash
   pip install pillow>=10.0.0
   pip install pyexiv2>=2.8.0
   ```

### Method 3: Virtual Environment (Advanced)

1. **Create a virtual environment**
   ```bash
   python -m venv venv
   ```

2. **Activate the virtual environment**
   - Windows:
     ```bash
     venv\Scripts\activate
     ```
   - macOS/Linux:
     ```bash
     source venv/bin/activate
     ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

## Troubleshooting Installation

### Issue: pyexiv2 installation fails

**On Windows:**
```bash
pip install pyexiv2 --only-binary :all:
```

**On Linux:**
```bash
sudo apt-get install libexiv2-dev libboost-python-dev
pip install pyexiv2
```

**On macOS:**
```bash
brew install exiv2 boost-python3
pip install pyexiv2
```

### Issue: tkinter not found

- **Windows/macOS**: tkinter is included with Python by default
- **Linux**: Install tkinter separately
  ```bash
  sudo apt-get install python3-tk
  ```

### Issue: Permission denied

**On Linux/macOS:**
```bash
pip install --user -r requirements.txt
```

Or use sudo (not recommended):
```bash
sudo pip install -r requirements.txt
```

### Issue: Old pip version

Update pip to the latest version:
```bash
python -m pip install --upgrade pip
```

## Verification

After installation, verify everything is working:

1. **Test the main application**
   ```bash
   python floriandheer_pipeline.py
   ```

2. **Check installed packages**
   ```bash
   pip list | grep -E "(pillow|pyexiv2)"
   ```

3. **Verify Python version**
   ```bash
   python --version
   ```
   Should show Python 3.8.0 or higher

## Next Steps

- See [README.md](../README.md) for usage instructions
- Check [CONFIGURATION.md](CONFIGURATION.md) for customization options
- Review [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues
