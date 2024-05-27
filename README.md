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

### Using generators and yielding gzip file line by line

In the initial implementation, I didn't prioritize processsing the gzip file faster and more efficiently. Now is the time to optimize the code. Luckily, the memray output highlights where the `big chunks` of data are. Checking those two functions will reduce the memory usage and improve the script's performance.

Downloading and reading the gzip file is a significant bottleneck when it comes to script's performance. Additionally, more memory-efficient data structures can be used by utilizing generators and iterators to reduce memory consumption during content parsing.

I changed the `read_gzip_contents` function to return an iterator instead of the entire file content, now yielding lines one by one. In addition to this change, when the user is not using a local file, the `requests.get` function in `download_contents_file` now includes the `stream=True` parameter to handle large downloads more efficiently.

Another change I added is updating the `parse_contents` function to process the Contents file line by line using an iterator, instead of parsing the whole content at once.

Here are the benchmark results:
```bash
$> ./package_statistics.py all
...
<Log Info>
...
2024-05-26 23:38:08,811 [INFO] main executed 5 times with an average time of 11.2538 seconds
```
More than 10 seconds faster with the scenario where we download the Contents file.

How about using the cache?
```bash
$> ./package_statistics.py --use-cache all
...
<Log Info>
...
2024-05-26 23:41:15,608 [INFO] main executed 5 times with an average time of 2.9649 seconds
```
It's 3.5-4 seconds faster on average.

Let's take a look at the flamegraphs from [memray-flamegraph-generators_and_yielding_second_phase.html](./memray-flamegraph-generators_and_yielding_second_phase.html). When I check the stats, the number of allocations increased vastly, to `(2038073)`. But the peak memory usage is now `72.6 MiB`.

The code is already faster and using significantly less memory right now.

Is there anything else I can do to run the code faster? I bet parsing the gzip content can be done in parallel. I'll investigate it in the next section.

### Trying Multithreading module

First, I tried Multithreading with parsing the contents line by line. That was the slowest among all my tests: The `./package_statistics.py --use-cache all` command executed 5 times with an average time of 81.3441 seconds. See git commit `b0c63e3` in the `multithreading-try` branch for further details.

Then, I implemented processing by chunks, which increased the speed vastly. Still, it wasn't as fast as regular processing approach with iterators and generators. I haven't seen any average runtime faster than 3.9 seconds. I've tried different chunk sizes and different number of threads, the result didn't improve.

Due to the Global Interpreter Lock (GIL), multithreading is not as effective for CPU-bound tasks as it is for I/O-bound tasks. Even though parsing lines from a file might seem like an I/O-bound task, frequent updates to a shared data structure (like the package counter) can cause contention and synchronization overhead. This can significantly slow down multithreaded programs, especially when threads are competing to update the shared defaultdict.

### Trying Multiprocessing module

Multiprocessing example parsing the contents line by line wasn't as dramatic as the multithreading example, but it was still slower: The `./package_statistics.py --use-cache all` command 5 times with an average time of 9.2875 seconds. See git commit `1f3f7bc` in the `multiprocessing-try` branch for further details.

Implementing chunks improved the performance of the code, but still it wasn't faster than 4 seconds in average. I've tried different chunk sizes and different number of CPUs, the result didn't improve.

Multiprocessing can overcome the limitations of the GIL by using separate memory spaces for each process. However, this comes with its own overheads. Processes are heavier than threads, and managing inter-process communication (IPC) and memory can be expensive. In this case, the cost of spawning multiple processes, splitting the data into chunks, and aggregating the results can outweigh the benefits of parallel processing, leading to slower overall performance.

## Summary:

The regular processing implementation with iterators and generators is highly efficient for this type of task. It minimizes memory usage and avoids the overhead of context switching, synchronization, and IPC. By processing the data in a single pass and using efficient data structures, this approach leverages Python’s strengths and minimizes overhead, resulting in faster execution times.

In this specific scenario, the regular processing approach with iterators and generators proves to be the most efficient due to its simplicity and the avoidance of the overheads associated with multithreading and multiprocessing. While multithreading and multiprocessing can offer performance improvements in certain contexts, the added complexity and overhead can sometimes negate these benefits, particularly for tasks that involve frequent updates to shared data structures or where the task is not sufficiently parallelizable.

I mainly prioritized improving the performance of the code over testing the individual functions. Due to the lack of time and the unexpected complexity of concurrency testing, I couldn’t find the opportunity to write tests for the individual functions to validate their behavior. Although the code is modular and functions are broken down into basic parts, the lack of tests is a significant concern for me in this implementation. If I had more time to spend on this task, writing comprehensive tests would be my top priority.

In total, the task took me 1.5 days on the weekend.
