import os.path
import re
from typing import List, Tuple, Optional, Set

from css_html_js_minify import html_minify, css_minify
from jinja2 import Environment, FileSystemLoader, select_autoescape, Template
from jsmin import jsmin
from slugify import slugify

import classes
from database import Database
from fmt_git_repository import FmtRepo


class Result:
    def __init__(self, commit_hash: str, commit_message: str, commit_timepoint: int):
        self.commit_hash: str = commit_hash
        self.commit_hash_short: str = commit_hash[0:8]
        self.commit_message: str = commit_message
        self.commit_timepoint: int = commit_timepoint
        self.benchmark_results: List[Tuple[str, float]] = []

    def get_benchmark(self, name: str):
        for benchmark_result in self.benchmark_results:
            if name == benchmark_result[0]:
                return benchmark_result[1]
        return 'NaN'

    def add_benchmark(self, name: str, result: float):
        self.benchmark_results.append((name, result))


def get_name(match: re.Match) -> str:
    try:
        return match.group('name')
    except IndexError:
        return match.group(0)


class Page:
    default_template_html: Template = None
    default_template_js: Template = None

    def __init__(self,
                 template_html: Template,
                 template_js: Optional[Template],
                 name: str,
                 description: str,
                 patterns: List[re.Pattern],
                 icon: str,
                 is_multi_axes: bool = False,
                 slug: Optional[str] = None):
        self.template_html: Template = template_html
        self.template_js: Optional[Template] = template_js

        self.name: str = name
        self.description: str = description
        self.patterns: List[re.Pattern] = patterns

        self.icon: str = icon

        self.slug: str = slugify(self.name) if slug is None else slug
        self.is_multi_axes: bool = is_multi_axes

    def get_match_or_none(self, result) -> Optional[re.Match]:
        matches = [re.match(pattern, result[2]) for pattern in self.patterns if re.match(pattern, result[2])]
        if len(matches) > 0:
            return matches[0]
        return None

    def filter_results(self, sorted_results):
        filtered_results = list()
        for result in sorted_results:
            if self.get_match_or_none(result) is not None:
                filtered_results.append(result)
        return filtered_results

    def generate(self, filtered_results, pages, fmt_repo: FmtRepo, db: Database, directory: str):
        benchmarks: List[str] = list()
        for result in filtered_results:
            match: re.Match = self.get_match_or_none(result)
            name = get_name(match)
            if name not in benchmarks:
                benchmarks.append(name)

        prepared_results: List[Result] = list()
        for result in filtered_results:
            found_prepared_results = [x for x in prepared_results if x.commit_hash == result[0]]
            if len(found_prepared_results) == 0:
                message = fmt_repo.get_commit_message(result[0])
                found_prepared_result = Result(result[0], message.split('\n', 1)[0], result[1])
                prepared_results.append(found_prepared_result)
            else:
                found_prepared_result = found_prepared_results[0]
            match: re.Match = self.get_match_or_none(result)
            name = get_name(match)
            found_prepared_result.add_benchmark(name, result[3])

        result_html = self.template_html.render(pages=pages,
                                                script_prefix=self.slug,
                                                current_page_name=self.name)
        result_html = html_minify(result_html)
        result_js = self.template_js.render(benchmarks=benchmarks,
                                            results=prepared_results,
                                            description=self.description,
                                            is_multi_axes=self.is_multi_axes)
        result_js = jsmin(result_js)
        with open(os.path.join(directory, '{}.html'.format(self.slug)), 'w') as html_file:
            html_file.write(result_html)
        with open(os.path.join(directory, 'script-{}.js'.format(self.slug)), 'w') as js_file:
            js_file.write(result_js)


class CompilationTimePage(Page):
    def __init__(self):
        Page.__init__(self,
                      template_html=Page.default_template_html,
                      template_js=Page.default_template_js,
                      name='Compilation time',
                      description='format.o compilation time',
                      patterns=[re.compile(r'^compilation_time$')],
                      icon='bi-stopwatch-fill')


class LibrarySizePage(Page):
    def __init__(self):
        Page.__init__(self,
                      template_html=Page.default_template_html,
                      template_js=Page.default_template_js,
                      name='Library size',
                      description='Size of libfmt, in bytes',
                      patterns=[re.compile(r'^static_library_size$'), re.compile(r'^shared_library_size$')],
                      icon='bi-file-earmark-zip-fill',
                      is_multi_axes=True)


class BenchmarkGroupPage(Page):
    def __init__(self, name: str, description: str, patterns: List[re.Pattern]):
        Page.__init__(self,
                      template_html=Page.default_template_html,
                      template_js=Page.default_template_js,
                      name=name,
                      description=description,
                      patterns=patterns,
                      icon='bi-bar-chart-fill')


class HomePage(Page):
    def __init__(self,
                 template_html: Template):
        Page.__init__(self,
                      template_html,
                      None,
                      'Home',
                      'Home page for this site',
                      [],
                      'bi-house-fill',
                      slug='index')

    def generate(self, filtered_results, pages, fmt_repo: FmtRepo, db: Database, directory: str):
        meta_values: List[Tuple[str, str]] = db.get_meta_values()
        bnchmrk_meta = None
        bnchmrk_generator_meta = None
        for meta_value in meta_values:
            if meta_value[0] == 'fmt_bnchmrk commit':
                bnchmrk_meta = meta_value
            elif meta_value[0] == 'fmt_bnchmrk_gnrtr commit':
                bnchmrk_generator_meta = meta_value
        meta_values.remove(bnchmrk_meta)
        meta_values.remove(bnchmrk_generator_meta)

        result_html = self.template_html.render(pages=pages,
                                                current_page_name=self.name,
                                                meta_values=meta_values,
                                                bnchmrk_meta=bnchmrk_meta,
                                                bnchmrk_generator_meta=bnchmrk_generator_meta)
        result_html = html_minify(result_html)
        with open(os.path.join(directory, '{}.html'.format(self.slug)), 'w') as html_file:
            html_file.write(result_html)


class SiteGenerator:
    def __init__(self):
        self.templates_path: str = 'site-templates'
        env = Environment(
            loader=FileSystemLoader(self.templates_path),
            autoescape=select_autoescape()
        )
        Page.default_template_html = env.get_template('page.html.jinja2')
        Page.default_template_js = env.get_template('script.js.jinja2')

        self.home_page_template_html: Template = env.get_template('index.html.jinja2')

    def generate(self, db: Database, fmt_repo: FmtRepo, runners: List[classes.Runner], pages_dir: str):
        assert len(runners) == 1  # not ready for multiple runners
        pages = list()

        # home page
        pages.append(HomePage(self.home_page_template_html))

        # stat pages
        pages.append(CompilationTimePage())
        pages.append(LibrarySizePage())

        # format_to pages
        pages.append(BenchmarkGroupPage(name='format_to • trivial • integral',
                                        description='fmt::format_to with "{}" format string and integral argument',
                                        patterns=[
                                            re.compile(r'^format_to_trivial_(?P<name>bool_type)$'),
                                            re.compile(r'^format_to_trivial_(?P<name>(u|)int(16|32|64))$'),
                                            re.compile(r'^format_to_trivial_(?P<name>std_byte)$'),
                                            re.compile(r'^format_to_trivial_(?P<name>pointer)$'),
                                        ]))
        pages.append(BenchmarkGroupPage(name='format_to • trivial • int128',
                                        description='fmt::format_to() with "{}" format string and int128 argument',
                                        patterns=[re.compile(r'^format_to_trivial_(?P<name>(u|)int128)$')]))
        pages.append(BenchmarkGroupPage(name='format_to • trivial • float',
                                        description='fmt::format_to() with "{}" format string and floating-point argument',
                                        patterns=[re.compile(r'^format_to_trivial_(?P<name>(float|double)_type)$')]))
        pages.append(BenchmarkGroupPage(name='format_to • trivial • long double',
                                        description='fmt::format_to() with "{}" format string and long double argument',
                                        patterns=[re.compile(r'^format_to_trivial_(?P<name>long_double_type)$')]))
        pages.append(BenchmarkGroupPage(name='format_to • trivial • string',
                                        description='fmt::format_to() with "{}" format string and string (or char) argument',
                                        patterns=[re.compile(
                                            r'^format_to_trivial_(?P<name>char_type|char_array|std_string|std_string_view)$')]))
        pages.append(BenchmarkGroupPage(name='format_to • specs • align, fill, zero, precision',
                                        description='fmt::format_to() with format string with various specs',
                                        patterns=[
                                            re.compile(r'^format_to_specs_(?P<name>align_.*)$'),
                                            re.compile(r'^format_to_specs_(?P<name>fill.*)$'),
                                            re.compile(r'^format_to_specs_(?P<name>zero_.*)$'),
                                            re.compile(r'^format_to_specs_(?P<name>precision_.*)$'),
                                        ]))
        pages.append(BenchmarkGroupPage(name='format_to • specs • sign',
                                        description='fmt::format_to() with format string with sign specs',
                                        patterns=[re.compile(r'^format_to_specs_sign_(?P<name>.*)$')]))
        pages.append(BenchmarkGroupPage(name='format_to • specs • types for integer',
                                        description='fmt::format_to() with format string with argument type specs for integer',
                                        patterns=[re.compile(r'^format_to_specs_type_(?P<name>.*)_integer$')]))
        pages.append(BenchmarkGroupPage(name='format_to • specs • types for float',
                                        description='fmt::format_to() with format string with argument type specs for float',
                                        patterns=[re.compile(r'^format_to_specs_type_(?P<name>.*)_float$')]))
        pages.append(BenchmarkGroupPage(name='format_to • args',
                                        description='fmt::format_to() with format string and 3 arguments',
                                        patterns=[re.compile(r'^format_to_args_(?P<name>.*)$')]))
        pages.append(BenchmarkGroupPage(name='format_to • chrono • general',
                                        description='fmt::format_to() with some general chrono format strings',
                                        patterns=[re.compile(
                                            r'^format_to_chrono_(?P<name>without_specs|with_specs_simple|with_specs_complex)$')]))
        pages.append(BenchmarkGroupPage(name='format_to • chrono • specs',
                                        description='fmt::format_to() with format string with specs',
                                        patterns=[re.compile(r'^format_to_chrono_(?P<name>((?!locale|with).)+)$')]))
        pages.append(BenchmarkGroupPage(name='format_to • chrono • locale',
                                        description='fmt::format_to() with format string with locale-specific specs',
                                        patterns=[re.compile(r'^format_to_chrono_(?P<name>\S+_locale)$')]))

        os.makedirs(pages_dir, exist_ok=True)

        with open(os.path.join(self.templates_path, 'style.css'), 'r') as css_in:
            with open(os.path.join(pages_dir, 'style.css'), 'w+') as css_out:
                css_out.write(css_minify(css_in.read()))

        sorted_results_from_db = db.get_results_for(runners[0].ID)
        sorted_results = list()
        unique_commits_hashes: Set[str] = set()
        for result in reversed(sorted_results_from_db):
            unique_commits_hashes.add(result[0])
            if len(unique_commits_hashes) > classes.commits_number_limit:
                break
            sorted_results.append(result)
        sorted_results.reverse()

        filtered_results_for_all_pages = list()
        for page in pages:
            filtered_results = page.filter_results(sorted_results)
            filtered_results_for_all_pages.extend(filtered_results)
            page.generate(filtered_results, pages, fmt_repo, db, pages_dir)

        # not_used_results = list(set(sorted_results) - set(filtered_results_for_all_pages))
        # not_used_results.sort()
        # print('not used results:')
        # for result in not_used_results:
        #     print('\t{}'.format(result[2]))
