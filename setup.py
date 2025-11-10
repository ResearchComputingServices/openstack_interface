from setuptools import setup, find_packages

setup(
    name='OpenStackInterface',
    version='1.0.0',

    packages=find_packages(),
    python_requires='>=3.7',
    install_requires=[  "openstacksdk>=1.0.0",
                        "pytest",],
    extras_require={'dev': ['pytest']},

    author='Nicholi Shiell',
    description='Interface for OpenStack services',
)
