"""Download verified official toolchains into an ignored workspace directory."""
import concurrent.futures,hashlib,json,urllib.request,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]/'tools/android-dev'
ROOT.mkdir(parents=True,exist_ok=True)

def fetch(url):
    request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(request,timeout=90) as response:return response.read()

def install(name,url,checksum,destination):
    archive=ROOT/(name+'.zip')
    if not archive.exists():archive.write_bytes(fetch(url))
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=checksum:raise RuntimeError(name+' checksum mismatch')
    target=ROOT/destination
    if not target.exists():
        with zipfile.ZipFile(archive) as package:package.extractall(target)
    print(name,'ready',flush=True)

if __name__=='__main__':
    jdk=json.loads(fetch('https://api.adoptium.net/v3/assets/latest/17/hotspot?architecture=x64&image_type=jdk&os=windows'))[0]['binary']['package']
    gradle_url='https://services.gradle.org/distributions/gradle-8.11.1-bin.zip'
    gradle_sha=fetch(gradle_url+'.sha256').decode().strip()
    packages=[('jdk',jdk['link'],jdk['checksum'],'jdk'),
              ('gradle',gradle_url,gradle_sha,'gradle'),
              ('sdk-tools','https://dl.google.com/android/repository/commandlinetools-win-13114758_latest.zip',
               '98b565cb657b012dae6794cefc0f66ae1efb4690c699b78a614b4a6a3505b003','sdk-tools')]
    with concurrent.futures.ThreadPoolExecutor(3) as executor:
        for result in executor.map(lambda item:install(*item),packages):pass
