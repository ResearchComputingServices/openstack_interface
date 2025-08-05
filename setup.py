from setuptools import setup, find_packages

setup(
    name='OpenStackInterface',
    version='1.0.0',
    packages=find_packages(),
    install_requires=[  "python-glanceclient==4.9.0",
                        "python-keystoneclient==5.6.0",
                        "python-neutronclient==11.6.0",
                        "python-novaclient==18.10.0",
                        "pytest",],
    extras_require={'dev': ['pytest']},
    author='Nicholi Shiell',
    description='Interface for OpenStack services',
    python_requires='>=3.7',
)