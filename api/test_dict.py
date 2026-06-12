import modal

jobs = modal.Dict.from_name("test-dict", create_if_missing=True)
try:
    jobs["foo"] = {"bar": "baz"}
    print(jobs["foo"])
except Exception as e:
    print("Error:", e)
