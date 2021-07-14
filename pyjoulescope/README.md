
# Joulescope Examples

Welcome to Joulescope™ scripting examples repository! 
Joulescope is an affordable, precision DC energy analyzer that enables you to 
build better products. Joulescope™ accurately and simultaneously measures the 
voltage and current supplied to your target device, and it then computes power 
and energy. For more information on Joulescope, see 
[www.joulescope.com](https://www.joulescope.com).

This joulescope-examples repository contains examples for how to use the
joulescope package in your own Python scripts and programs.  

If you just want to use Joulescope, you can 
[download](https://www.joulescope.com/download) the application.


## Quick start


### Verify Python installation

Verify that Python 3.6+ is installed on your computer:

    python3 -VV
    
On Windows, "python3" may not be created by default.  You can try "python -V -V"
if your path is configured correctly, or you can provide the full path to your
python executable.  If python is not already installed on your platform, 
we recommend:

*   Windows: download & install the [official Python release](https://www.python.org/downloads/).
*   macOS: install [brew](https://brew.sh/), then "brew install python"
*   Ubuntu 18.04 LTS: sudo apt install python3


### Get this code

Clone this repository to your computer:

    git clone https://github.com/jetperch/pyjoulescope_examples.git

Alternatively, you can just 
[download the latest](https://github.com/jetperch/pyjoulescope_examples/archive/master.zip) 
version directly from GitHub, and then extract the ZIP file.

Next, cd into the repository directory:

    cd pyjoulescope_examples
    
and install the dependencies:

    pip3 install -U -r requirements.txt

Note that some examples use matplotlib, so be sure to run this last command!

    
### Use this code:

Open a command terminal and run the scripts of your choice.  See the bin
directory for the list of scripts.  For example:

    python3 bin\capture_simple.py

For scripts that take arguments, specify a "--help" argument for details on
the available arguments:

    python3 bin\downsample_logging.py --help

Many of the scripts also have instructions inside the script.  Use your 
favorite text editor to open the script.


## License

All pyjoulescope_example code is released under the permissive Apache 2.0 
license.  See the [License File](LICENSE.txt) for details.
