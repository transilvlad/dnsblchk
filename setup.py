from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="dnsblchk",
    version="1.0.0",
    author="DNSBL Checker",
    author_email="contact@example.com",
    description="A DNS Blacklist Checker service.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/example/dnsblchk",
    packages=find_packages(exclude=["test", "test.*"]),
    include_package_data=True,
    install_requires=[
        "pyyaml",
        "dnspython",
    ],
    entry_points={
        "console_scripts": [
            "dnsblchk=main:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
    ],
    python_requires='>=3.6',
    data_files=[
        ('/etc/dnsblchk', ['config/config.yaml.template']),
        ('/usr/lib/systemd/system', ['dnsblchk.service']),
    ]
)

