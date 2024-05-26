# DEBIAN PACKAGE STATISTICS by Serdar Dalgiç

`package_statistics.py` is a simple python command line tool to print the statistics of debian packages with respect to their number of files.

## Problem Description

Debian uses *deb packages to deploy and upgrade software. The packages are stored in repositories and each repository contains the so called "Contents index". The format of that file is well described here https://wiki.debian.org/RepositoryFormat#A.22Contents.22_indices

Your task is to develop a python command line tool that takes the architecture (amd64, arm64, mips etc.) as an argument and downloads the compressed Contents file associated with it from a Debian mirror. The program should parse the file and output the statistics of the top 10 packages that have the most files associated with them. An example output could be:

```
./package_statistics.py amd64



<package name 1>         <number of files>
<package name 2>         <number of files>
......

<package name 10>         <number of files>
```

You can use the following Debian mirror: http://ftp.uk.debian.org/debian/dists/stable/main/. Please try to follow Python's best practices in your solution. Hint: there are tools that can help you verify your code is compliant. In-line comments are appreciated.

Please do your work in a local Git repository. Your repo should contain a README that explains your thought process and approach to the problem, and roughly how much time you spent on the exercise. When you are finished, create a tar.gz of your repo and submit it to the link included in this email. Please do not make the repository publicly available.

Note: We are interested not only in quality code, but also in seeing your approach to the problem and how you organize your work.

## Installation and Use

This script uses [requests](https://requests.readthedocs.io/) library to download the Contents files. That's why `requests` has to be installed on your system.

Add the script to your runpath or create a virtual environment with the given [requirements](./requirements) file.

I personally use [uv](https://pypi.org/project/uv/) for managing python environments.

```
$> uv venv venv-canonical # you can change `venv-canonical` to your preferred virtualenv name
$> source venv-canonical/bin/activate
$> uv pip install -r requirements
...
$> ./package_statistics.py amd64
Top 10 packages with the most files:
1. devel/piglit                   53007
2. science/esys-particle          18408
3. math/acl2-books                16907
4. libdevel/libboost1.81-dev      15456
5. libdevel/libboost1.74-dev      14333
6. lisp/racket                    9599
7. net/zoneminder                 8161
8. electronics/horizon-eda        8130
9. libdevel/libtorch-dev          8089
10. libdevel/liboce-modeling-dev   7458
```
For simplicity, the package names also include the section part before the '/'.
For benchmarking the code, helper functions in the [benchmarking.py module](./benchmarking.py), and [memray](https://bloomberg.github.io/memray/) memory profiler are used.

Memray is included in the requirements file.

## Evolution of the code

I took the approach of solving this problem iteratively. I will try to explain my approach and how I compared the results in the following sections.

I compared my output with the output of the following Bash oneliner:
```bash
gunzip -c Contents-<architecture>.gz | awk '{print $NF}' | tr ',' '\n' | grep -v '^$' | sort | uniq -c | sort -rn | head -10
```

The benchmarks and calculations are done on my personal computer, MacBook Air M1 2020, 16GB Memory, and 8 CPUs.

### Initial implementation

First, I wrote a script that simply does what it's supposed to do.
1. Takes necessary arguments and figures out which Contents file to reach
2. Downloads the file and parses the contents. Alternatively, user can provide a local file to skip the downloading.
3. Sorts the packages and finds the top 10 package names with the most filenames.

I ran the script with `@benchmark_with_repeater(repeats=5)` decorator on main function
```bash
$> ./package_statistics.py all
...
<Log Info>
...
2024-05-26 21:48:55,633 [INFO] main executed 5 times with an average time of 21.2306 seconds

$> ./package_statistics.py --use-cache all
...
<Log Info>
...
2024-05-26 21:52:59,684 [INFO] main executed 5 times with an average time of 6.8130 seconds
```

For memory usage, I created flamegraphs with memray with the following commands:
```bash
$> memray run -o initial_version.bin package_statistics.py all
...
<Log Info>
...
2024-05-26 21:59:07,754 [INFO] main executed 5 times with an average time of 21.6504 seconds
[memray] Successfully generated profile results.

You can now generate reports from the stored allocation records.
Some example commands to generate reports:

/Users/serdar/tmp/Canonical-tech-assessment/SerdarDalgic-CanonicalPackageStats/venv-canonical/bin/python -m memray flamegraph initial_version.bin

$> python -m memray flamegraph initial_version.bin
Wrote memray-flamegraph-initial_version.html
```

You can open the [memray-flamegraph-initial_version.html](./memray-flamegraph-initial_version.html) file to see the profiler graphs and memory usages.
In short, it makes a lot of allocations `(228667)` and the peak memory usage is `3.1 GiB`.
I'll take a deeper look into those two parts of the code:
```python
contents = read_gzip_contents(content_bytes)
# and
package_counter = parse_contents(contents)
```
