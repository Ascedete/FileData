from setuptools import setup, find_packages

setup(
    name="FileData",
    version="0.1",
    description="Process files and multiline strings with additional information such as current linenumber",
    author="PTS",
    packages=find_packages("filedata", exclude="test"),
)