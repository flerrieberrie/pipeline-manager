# Changelog

All notable changes to the Florian Dheer Pipeline Manager will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.0] - 2025-01-27

### Added
- Professional project structure with proper documentation
- Comprehensive README.md with installation and usage instructions
- .gitignore file for version control
- LICENSE file
- CHANGELOG.md for version tracking
- docs/, tests/, and config/ directories for better organization
- Documentation: INSTALLATION.md, CONFIGURATION.md, CONTRIBUTING.md, QUICK_START.md
- Organized assets into dedicated folder

### Changed
- Updated requirements.txt to include missing pyexiv2 dependency
- Removed unused web framework dependencies (FastAPI, uvicorn, etc.)
- Cleaned up requirements to only include actively used packages
- Moved logo and favicon to assets/ directory
- Reorganized project to follow Python best practices

### Fixed
- Missing pyexiv2 dependency that caused metadata scripts to fail

## [0.4.0] - 2024-10-18

### Added
- Professional dark-themed UI
- Category-based script organization
- Multi-threaded script execution
- Enhanced error handling and logging

### Changed
- Reorganized scripts into category-based structure
- Improved user experience with better visual feedback

## [0.3.0] - 2024-09-03

### Added
- Initial pipeline manager with GUI
- Basic script launcher functionality
- Core pipeline scripts for various workflows
- Enhanced dependency installer

---

## Version Numbering

- **Major version** (X.0.0): Incompatible API changes or major redesigns
- **Minor version** (0.X.0): New features, backwards compatible
- **Patch version** (0.0.X): Bug fixes, backwards compatible
