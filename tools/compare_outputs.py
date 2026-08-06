import glob
import json
import os
import sys


def _deep_diff(prefix, a, b, diffs):
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            if key not in a:
                diffs.append("%s.%s: missing in first (%r)" % (prefix, key, b[key]))
            elif key not in b:
                diffs.append("%s.%s: missing in second (%r)" % (prefix, key, a[key]))
            else:
                _deep_diff("%s.%s" % (prefix, key), a[key], b[key], diffs)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            diffs.append("%s: list length %d != %d" % (prefix, len(a), len(b)))
        for i, (x, y) in enumerate(zip(a, b)):
            _deep_diff("%s[%d]" % (prefix, i), x, y, diffs)
    else:
        if a != b:
            diffs.append("%s: %r != %r" % (prefix, a, b))


def compare(a_dir, b_dir):
    files_a = sorted(glob.glob(os.path.join(a_dir, "*.json")))
    files_b = sorted(glob.glob(os.path.join(b_dir, "*.json")))
    names_a = {os.path.basename(p) for p in files_a}
    names_b = {os.path.basename(p) for p in files_b}

    diffs = []
    only_a = sorted(names_a - names_b)
    only_b = sorted(names_b - names_a)
    if only_a:
        diffs.append("files only in first: %s" % ", ".join(only_a))
    if only_b:
        diffs.append("files only in second: %s" % ", ".join(only_b))

    for name in sorted(names_a & names_b):
        path_a = os.path.join(a_dir, name)
        path_b = os.path.join(b_dir, name)
        with open(path_a, encoding="utf-8") as f:
            raw_a = f.read()
        with open(path_b, encoding="utf-8") as f:
            raw_b = f.read()
        if raw_a == raw_b:
            continue
        diffs.append("%s: content differs" % name)
        try:
            _deep_diff(name, json.loads(raw_a), json.loads(raw_b), diffs)
        except Exception as exc:
            diffs.append("%s: could not deep-compare (%s)" % (name, exc))
    return diffs


def main():
    a_dir = sys.argv[1] if len(sys.argv) > 1 else ".backup_t1"
    b_dir = sys.argv[2] if len(sys.argv) > 2 else "output"
    diffs = compare(a_dir, b_dir)
    if not diffs:
        print("NO DIFFERENCES between %s and %s" % (a_dir, b_dir))
        return 0
    print("DIFFERENCES FOUND (%d):" % len(diffs))
    for diff in diffs:
        print("  " + diff)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
