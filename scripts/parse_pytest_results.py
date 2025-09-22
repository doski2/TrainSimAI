#!/usr/bin/env python3
"""Parse pytest JUnit XML and print a concise summary and up to 20 failure details.
Usage: python scripts/parse_pytest_results.py [path/to/pytest-results.xml]
"""
import sys
from xml.etree import ElementTree as ET

path = sys.argv[1] if len(sys.argv) > 1 else "artifacts/pytest-results.xml"
try:
    tree = ET.parse(path)
except Exception as e:
    print(f"ERROR: cannot parse XML {path}: {e}")
    sys.exit(2)

root = tree.getroot()
if root.tag == 'testsuites':
    suites = list(root.findall('testsuite'))
else:
    suites = [root]

total_tests = 0
total_failures = 0
total_errors = 0
total_skipped = 0
total_time = 0.0
failures = []

for s in suites:
    t = int(s.attrib.get('tests', '0'))
    f = int(s.attrib.get('failures', '0'))
    e = int(s.attrib.get('errors', '0'))
    sk = int(s.attrib.get('skipped', '0'))
    time = float(s.attrib.get('time', '0'))
    total_tests += t
    total_failures += f
    total_errors += e
    total_skipped += sk
    total_time += time
    for case in s.findall('testcase'):
        tcname = case.attrib.get('name')
        classname = case.attrib.get('classname')
        ctime = case.attrib.get('time', '0')
        # check for failure or error
        failure = case.find('failure')
        error = case.find('error')
        skipped = case.find('skipped')
        if failure is not None or error is not None:
            node = failure if failure is not None else error
            typ = 'failure' if failure is not None else 'error'
            msg = node.attrib.get('message', '')
            txt = (node.text or '').strip()
            failures.append({
                'classname': classname,
                'name': tcname,
                'type': typ,
                'message': msg,
                'text': txt,
                'time': ctime,
            })

print('Pytest JUnit XML summary for', path)
print('----------------------------------------')
print(f'Total tests: {total_tests}')
print(f'Failures: {total_failures}  Errors: {total_errors}  Skipped: {total_skipped}')
print(f'Total time: {total_time:.2f}s')
print('')
if failures:
    print(f'Found {len(failures)} failing tests (showing up to 20):')
    for i, f in enumerate(failures[:20], 1):
        print('----')
        print(f"{i}. {f['classname']}::{f['name']} [{f['type']}] (time={f['time']})")
        print('message:', f['message'])
        if f['text']:
            print('text:')
            print(f['text'])
else:
    print('No failing tests found.')

# exit code 0
