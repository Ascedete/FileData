from setuptools import setup

setup(
    name="FileData",
    version="0.1.7",
    description="Process files and multiline strings with additional information such as current linenumber",
    author="PTS",
    packages=["filedata"],
    install_requires=["Result @ git+https://github.com/Ascedete/Result.git@master"],
    tests_require=["pytest"],
)
