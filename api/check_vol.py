import modal
import os
app = modal.App("check-vol")
vol = modal.Volume.from_name("comfy-models-disk")

@app.function(volumes={"/models": vol})
def ls():
    print("Contents of /models:")
    os.system("ls -la /models")
    print("Contents of /models/checkpoints:")
    os.system("ls -la /models/checkpoints")

@app.local_entrypoint()
def main():
    ls.remote()
