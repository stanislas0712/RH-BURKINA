import glob, xml.dom.minidom as m
# 1. Python compile check
import py_compile
py_files = glob.glob(r"custom_addons/rh_burkina/**/*.py", recursive=True)
failed = []
for f in py_files:
    try:
        py_compile.compile(f, doraise=True)
    except py_compile.PyCompileError as e:
        failed.append((f, str(e)))
if failed:
    print("PY_COMPILE_FAIL")
    for f, e in failed:
        print(f, "->", e)
else:
    print("PY_COMPILE_OK (%d files)" % len(py_files))
# 2. XML parse check
xml_files = glob.glob(r"custom_addons/rh_burkina/**/*.xml", recursive=True)
bad = []
for f in xml_files:
    try:
        m.parse(f)
    except Exception as e:
        bad.append((f, str(e)))
if bad:
    print("XML_PARSE_FAIL")
    for f, e in bad:
        print(f, "->", e)
else:
    print("XML_PARSE_OK (%d files)" % len(xml_files))
