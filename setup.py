from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="odoo_xmlrpc_wrapper",
    version="1.0.1",
    description="A simple Python library to make CRUD process easier.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/cagatayuresin/odoo-xmlrpc-wrapper",
    author="Cagatay URESIN",
    author_email="cagatayuresin@gmail.com",
    license="MIT",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Framework :: Odoo",
        "Framework :: Odoo :: 16.0",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: Freeware",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.7",
        "Topic :: Office/Business",
        "Topic :: Software Development :: Libraries",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.7",
    keywords="odoo external api xmlrpc rpc wrapper",
)
