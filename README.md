## Generator of [{fmt}](https://github.com/fmtlib/fmt) benchmark results

This project creates the nice output for [fmt_bnchmrk](https://github.com/alexezeder/fmt_bnchmrk) - just 
[check it out](https://alexezeder.github.io/fmt_bnchmrk).

### How to run

**Please consider reading entire README.md before running this script.**

These packages should be installed in your system:

* `git`
* `python3` (with `pip` and `venv`)
* `docker`
* `sqlite3`

Use `venv` and `pip` to install dependencies without polluting system.
```bash
python3 -m venv venv
source venv/bin/activate
python3 -m pip install -r requirements.txt
```

Current workflow of the `main.py` script (which is the entrypoint by the way):

* clone fmt_bnchmrk
* clone {fmt} repo
* initialize docker and build all runners from `runners` folder (currently only `gcc-11`)

  _this step creates docker images (names are `fmt_bnchmrk:<runner_name>`) in your system, be prepared_

* prepare SQLite DB for the current config
* while one of last `N` commits of {fmt} or newer:
  * run task in docker for this commit
  * upload results to fmt_bnchmrk Pages


### Feel free to open issues and PRs.
