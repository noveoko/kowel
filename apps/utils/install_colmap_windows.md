# How to Install COLMAP on Windows

## Prerequisites
- Windows 10 or 11 (64-bit)
- Administrator privileges
- At least 8GB RAM recommended
- Graphics card with CUDA support (optional, but recommended for better performance)

## Method 1: Using Pre-built Binary (Recommended)

1. **Download COLMAP**
   - Visit the official COLMAP releases page: https://github.com/colmap/colmap/releases
   - Download the latest Windows binary (e.g., `COLMAP-3.8-windows.zip`)
   - Look for a file named like `COLMAP-X.X-windows.zip` where X.X is the version number

2. **Extract the Archive**
   - Right-click the downloaded ZIP file
   - Select "Extract All..."
   - Choose a destination folder (e.g., `C:\Program Files\COLMAP`)
   - Click "Extract"

3. **Install Visual C++ Redistributable**
   - Download the latest Visual C++ Redistributable from Microsoft's website
   - Install both x64 and x86 versions if prompted
   - Restart your computer after installation

4. **Set Up Environment Variables**
   - Right-click on "This PC" or "My Computer"
   - Select "Properties"
   - Click "Advanced system settings"
   - Click "Environment Variables"
   - Under "System Variables," find "Path"
   - Click "Edit"
   - Click "New"
   - Add the path to your COLMAP installation (e.g., `C:\Program Files\COLMAP`)
   - Click "OK" on all windows

## Method 2: Building from Source

### Install Required Tools

1. **Visual Studio**
   - Download Visual Studio 2019 or later from Microsoft's website
   - During installation, select:
     - "Desktop development with C++"
     - "Windows 10 SDK"
     - "C++ CMake tools for Windows"

2. **CMake**
   - Download CMake from https://cmake.org/download/
   - Choose the Windows x64 installer
   - During installation, select "Add CMake to system PATH"

3. **Git**
   - Download Git from https://git-scm.com/download/win
   - Use default installation options

### Build Process

1. **Clone Repository**
   ```batch
   git clone https://github.com/colmap/colmap.git
   cd colmap
   git submodule update --init --recursive
   ```

2. **Configure Build**
   ```batch
   mkdir build
   cd build
   cmake -G "Visual Studio 16 2019" -A x64 -DCMAKE_BUILD_TYPE=Release ..
   ```

3. **Build COLMAP**
   ```batch
   cmake --build . --config Release
   ```

4. **Install**
   ```batch
   cmake --install . --config Release
   ```

## Verifying Installation

1. Open Command Prompt
2. Type `colmap -h`
3. If installed correctly, you should see the COLMAP help message

## Common Issues and Solutions

### Missing DLL Errors
- Install Visual C++ Redistributable packages
- Ensure all dependencies are in system PATH
- Try running as administrator

### CUDA Issues
- Install NVIDIA GPU drivers
- Install CUDA Toolkit if using GPU features
- Verify CUDA installation with `nvidia-smi` command

### Build Errors
- Ensure all prerequisites are installed
- Check Visual Studio installation is complete
- Verify CMake version is 3.10 or higher

## Optional: CUDA Support

To enable CUDA support (recommended for better performance):

1. Install NVIDIA GPU drivers
2. Download and install CUDA Toolkit from NVIDIA website
3. Add CUDA to system PATH
4. If building from source, add `-DCUDA_ENABLED=ON` to CMake configuration

## Testing Installation

1. Create a test project:
   ```batch
   mkdir test_project
   cd test_project
   ```

2. Run COLMAP GUI:
   ```batch
   colmap gui
   ```

3. If the GUI opens successfully, your installation is working

## Next Steps

After successful installation:
- Read the official COLMAP documentation
- Try the tutorial projects
- Join the COLMAP user group for support
- Keep the software updated by checking for new releases

## Support Resources

- Official Documentation: https://colmap.github.io/
- GitHub Issues: https://github.com/colmap/colmap/issues
- User Group: https://groups.google.com/forum/#!forum/colmap