from setuptools import setup, find_packages

setup(
    name='Scanly',
    version='0.1.0',
    author='Your Name',
    author_email='amcgreadyfreelance@gmail.com',
    description='A media file monitoring and organization tool',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/amcgready/Scanly',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    install_requires=[
        'requests',  # For API calls
        'watchdog',  # For monitoring file system changes
        # Add other dependencies as needed
    ],
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.6',
)