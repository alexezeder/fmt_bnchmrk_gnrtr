#!/usr/bin/env python3
import argparse
import glob
import hashlib
import json
import os
import re
import tempfile
import time
from typing import List, Tuple, Optional

import git
from docker import DockerClient, from_env, errors

from classes import Runner, Commit, Config
from database import Database
from fmt_bnchmrk_git_repository import FmtBnchmrkRepo
from fmt_git_repository import FmtRepo
from site_generator import SiteGenerator
from tools import StepPrinter


def get_image_name_for_runner(runner_name: str) -> str:
    return 'fmt_bnchmrk:{}'.format(runner_name)


def get_stat_results(temp_dir_name: str) -> List[Tuple[str, float]]:
    results = list()
    compilation_time_total: float = 0.0
    files = glob.glob(os.path.join(temp_dir_name, 'compilation_time_*.txt'))
    for file_path in files:
        with open(file_path, 'r') as result_txt:
            lines = [line.rstrip() for line in result_txt]
            for line in lines:
                match = re.match(r"^real\t(\d+)m([\d.]+)s", line)
                if match:
                    minutes = float(match.group(1))
                    seconds = float(match.group(2))
                    compilation_time_total += seconds + minutes * 60
    compilation_time = compilation_time_total / len(files)
    results.append(('compilation_time', compilation_time))

    with open(os.path.join(temp_dir_name, 'static_library_size.txt'), 'r') as result_txt:
        library_size = int(result_txt.read())
        results.append(('static_library_size', library_size))

    with open(os.path.join(temp_dir_name, 'shared_library_size.txt'), 'r') as result_txt:
        library_size = int(result_txt.read())
        results.append(('shared_library_size', library_size))

    return results


def get_suites_results(temp_dir_name: str) -> List[Tuple[str, float]]:
    files: List[str] = glob.glob(os.path.join(temp_dir_name, '*.json'))

    class Result:
        def __init__(self, name: str, amount: int, time: float):
            self.name: str = name
            self.amount: int = amount
            self.time: float = time

    results: List[Result] = list()
    for file_path in files:
        with open(file_path, 'r') as results_json:
            parsed = json.load(results_json)
            for benchmark in parsed['benchmarks']:
                result_name = str(benchmark['name'])
                result_time = float(benchmark['real_time'])
                filtered_results: List[Result] = [result for result in results if result.name == result_name]
                if len(filtered_results) == 0:
                    results.append(Result(result_name, 1, result_time))
                else:
                    filtered_results[0].time += result_time
                    filtered_results[0].amount += 1

    return [(result.name, result.time / result.amount) for result in results]


def execute_task(docker_client: DockerClient, fmt_repo: FmtRepo, fmt_bnchmrk_repo: FmtBnchmrkRepo, commit: Commit,
                 runner: Runner, config: Config) -> Optional[List[Tuple[str, float]]]:
    fmt_repo.set_current_commit(commit.hash)

    temp_dir = tempfile.TemporaryDirectory()
    temp_dir_name = temp_dir.name
    volumes = {
        fmt_repo.get_directory(): {'bind': '/fmt', 'mode': 'ro'},
        fmt_bnchmrk_repo.get_directory(): {'bind': '/benchmarks', 'mode': 'ro'},
        temp_dir_name: {'bind': '/output', 'mode': 'rw'}
    }
    environment = {
        "RUNNER_MAX_THREADS": config.max_threads,
        "RUNNER_COMPILATION_RUNS": config.compilation_runs,
        "RUNNER_COMPILATION_PAUSE": config.compilations_pause,
        "RUNNER_BENCHMARK_RUNS": config.benchmark_runs,
    }

    try:
        docker_client.containers.run(get_image_name_for_runner(runner.name),
                                     detach=False, volumes=volumes, environment=environment, remove=True)
    except errors.ContainerError:
        if config.skip_faulty_commits:
            return None
        else:
            raise

    results = get_stat_results(temp_dir_name)
    results.extend(get_suites_results(temp_dir_name))
    return results


def run(config: Config):
    with StepPrinter('Preparing fmt_bnchmrk repository'):
        fmt_bnchmrk_repo = FmtBnchmrkRepo()
    with StepPrinter('Preparing {fmt} repository'):
        fmt_repo = FmtRepo()
    with StepPrinter('Preparing site generator'):
        site_generator = SiteGenerator()
    with StepPrinter('Initializing Docker client'):
        docker_client = from_env()
    with StepPrinter('Preparing runners'):
        runner_directories = glob.glob('runners/*')
        runners: List[Runner] = list()
        for runner_directory in runner_directories:
            tag_name = os.path.basename(runner_directory)
            image = docker_client.images.build(path=runner_directory,
                                               tag=get_image_name_for_runner(tag_name),
                                               rm=True)[0]
            description = image.labels['description']
            runners.append(Runner(tag_name, description, image.id))

    with StepPrinter('Preparing components info'):
        bnchmrk_commit_hash: str = fmt_bnchmrk_repo.get_commit_hash()
        gnrtr_commit_hash: str = git.Repo('.').commit('HEAD').hexsha
        hash_md5 = hashlib.md5()
        hash_md5.update(bnchmrk_commit_hash.encode('utf-8'))
        hash_md5.update(gnrtr_commit_hash.encode('utf-8'))
        hash_md5.update(config.as_bytes())
        for runner in runners:
            hash_md5.update(runner.docker_ID.encode('utf-8'))
        final_components_hash: str = hash_md5.hexdigest()

    with StepPrinter('Preparing database'):
        db = Database(config, final_components_hash, bnchmrk_commit_hash, gnrtr_commit_hash)
    with db, StepPrinter('Synchronizing runners info with database'):
        db.synchronize_runners(runners)

    last_hash: str = ''
    while True:
        with StepPrinter('Updating {fmt} repository'):
            fmt_repo.update()
            commits = fmt_repo.get_available_commits()
        with db, StepPrinter('Updating commits info from the database'):
            db.update_commits(commits)

        has_non_processed_commits: bool = len([x for x in commits if not x.is_processed]) > 0
        if has_non_processed_commits:
            for commit in commits:
                for runner in runners:
                    if commit.is_processed:
                        continue
                    with StepPrinter('Executing task on commit "{}" with runner "{}"'.format(commit.hash, runner.name)):
                        results = execute_task(docker_client, fmt_repo, fmt_bnchmrk_repo, commit, runner, config)
                    with db, StepPrinter('Saving results to database'):
                        db.save_results(commit, runner, results)

                new_hash: str = db.calculate_hash()
                if last_hash != new_hash:
                    if config.website_output_dir is None:
                        temp_dir = tempfile.TemporaryDirectory()
                        website_dir = temp_dir.name
                    else:
                        website_dir = config.website_output_dir
                    with db, StepPrinter('Generating website'):
                        site_generator.generate(db, fmt_repo, runners, website_dir)
                        if config.commit_bnchmrk_pages:
                            fmt_bnchmrk_repo.commit_pages(website_dir)
                        last_hash = new_hash
        else:
            with StepPrinter('Sleeping'):
                time.sleep(config.sleep_time)


def main():
    def boolean_string(s):
        return s in {'True', 'true', '1', 'on', 'yes', 'y'}

    parser = argparse.ArgumentParser(description='Generation of fmt_bnchmrk HTML result pages',
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('--max-threads', dest='max_threads', type=int, default=Config.default_max_threads,
                        help='maximum amount of threads for library and benchmarks building\n(default: {})'.format(
                            Config.default_max_threads))
    parser.add_argument('--compilation-runs', dest='compilation_runs', type=int,
                        default=Config.default_compilation_runs,
                        help='amount of library compilations (average compilation time calculated in this case)\n'
                             '(default: {})'.format(Config.default_compilation_runs))
    parser.add_argument('--compilations-pause', dest='compilations_pause', type=float,
                        default=Config.default_compilations_pause,
                        help='pause between each library compilation procedure\n(default: {})'.format(
                            Config.default_compilations_pause))
    parser.add_argument('--benchmark-runs', dest='benchmark_runs', type=int, default=Config.default_benchmark_runs,
                        help='amount of each benchmark suite runs (average time calculated in this case)\n'
                             '(default: {})'.format(Config.default_benchmark_runs))
    parser.add_argument('--sleep-time', dest='sleep_time', type=int, default=Config.default_sleep_time,
                        help='sleep time, when no new commits found\n(default: {})'.format(Config.default_sleep_time))
    parser.add_argument('--commit-bnchmrk-pages', dest='commit_bnchmrk_pages', type=boolean_string,
                        default=Config.default_commit_bnchmrk_pages,
                        help='in case if you have an access to fmt_bnchmrk repo, if not provided, then local website '
                             'is generated\n(default: false)')
    parser.add_argument('--website-output-dir', dest='website_output_dir', type=str,
                        default=Config.default_website_output_dir,
                        help='in case if you don\'t have an access to fmt_bnchmrk repo or you want to generate website '
                             'locally (ignored if --commit-bnchmrk-pages provided)\n'
                             '(default: "{}")'.format(Config.default_website_output_dir))
    parser.add_argument('--database-dir', dest='database_dir', type=str, default=Config.default_database_dir,
                        help='directory to save database file\n(default: "{}")'.format(Config.default_database_dir))
    parser.add_argument('--skip-faulty-commits', dest='skip_faulty_commits', type=boolean_string,
                        default=Config.default_skip_faulty_commits,
                        help='skip commits that cannot be processed\n'
                             '(default: "{}")'.format(Config.default_skip_faulty_commits))

    args = parser.parse_args()
    config: Config = Config(args.max_threads, args.compilation_runs, args.compilations_pause, args.benchmark_runs,
                            args.sleep_time, args.commit_bnchmrk_pages, args.website_output_dir, args.database_dir,
                            args.skip_faulty_commits)
    run(config)


if __name__ == '__main__':
    main()
