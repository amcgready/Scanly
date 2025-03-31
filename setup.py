from setuptools import setup, find_packages

setup(
    name='Scanly',
    version='0.1.0',
    author='Adam McGready',
    author_email='amcgreadyfreelance@gmail.com',
    description='A media file monitoring and organization tool with symlink and hardlink support',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/amcgready/Scanly',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    install_requires=[
        'requests',      # For API calls
        'watchdog',      # For monitoring file system changes
        'tqdm>=4.64.0',  # For progress bars
        'python-dotenv', # For environment configuration
        'tmdbv3api',     # For TMDB integration
    ],
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.6',
)