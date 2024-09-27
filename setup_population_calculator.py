from setuptools import setup, Extension
import pybind11

# Define the GDAL include and library paths
gdal_include_dirs = ['/usr/include/gdal']  # Adjust this path based on your GDAL installation
gdal_library_dirs = ['/usr/lib']  # Adjust this path based on your GDAL installation

# Define the C++ extension module
ext_modules = [
    Extension(
        'population_calculator',
        sources=['population_calculator.cpp'],
        include_dirs=[
            pybind11.get_include(),
            *gdal_include_dirs  # Add GDAL include dirs
        ],
        library_dirs=gdal_library_dirs,  # Add GDAL library dirs
        libraries=['gdal', 'jsoncpp'],  # Link against GDAL and JSONCPP libraries
        extra_compile_args=['-std=c++11']
    )
]

setup(
    name='population_calculator',
    version='0.1',
    ext_modules=ext_modules,
)
