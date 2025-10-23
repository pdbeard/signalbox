from setuptools import setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="signalbox",
    version="0.1.0",
    author="pdbeard",
    description="Script execution control and monitoring",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/pdbeard/signalbox",
    py_modules=["main"],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Topic :: System :: Systems Administration",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    install_requires=[
        "click>=8.0.0",
        "PyYAML>=5.4.0",
    ],
    entry_points={
        "console_scripts": [
            "signalbox=main:cli",
        ],
    },
)
