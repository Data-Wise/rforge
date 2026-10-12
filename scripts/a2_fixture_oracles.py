"""Separate-process real R/HTTP oracles, bound to committed fixture expectations."""
from __future__ import annotations
import hashlib
import http.server
import json
import os
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path
from lib import _docexamples, _docsite


def package(path,readme):
    path.mkdir(parents=True)
    (path/'DESCRIPTION').write_text('Package: a2oracle\nVersion: 0.0.1\nTitle: Fixture\nDescription: A controlled fixture.\nLicense: MIT\nAuthors@R: person("A", "Fixture", email="fixture@example.org", role=c("aut", "cre"))\n')
    (path/'NAMESPACE').write_text('')
    (path/'README.md').write_text(readme)
    (path/'R').mkdir();(path/'R'/'f.R').write_text('f <- function() 1\n')


def identities(findings):
    return [{key:f[key] for key in ('check','severity','file','assertion_id') if key in f} for f in findings]


def collect(directory):
    expected=json.loads(Path('tests/a2/expected-findings.json').read_text())
    if expected.get('status')!='ready':raise ValueError('Fixture expectations pending')
    fixtures=[]
    for name,number in (('examples-clean','0.19'),('examples-planted','0.80')):
        pkg=directory/name;sentinel=directory/(name+'.sentinel');nonce=uuid.uuid4().hex
        code=f'```r\nwriteLines("{nonce}", {json.dumps(str(sentinel))})\nprint(0.19)\n#> [1] {number}\n```\n'
        package(pkg,code)
        report=_docexamples.audit(pkg,deadline=time.monotonic_ns()+20_000_000_000)
        oracle=expected['fixtures'][name]
        if report['state']!='complete' or report['counts']['checked']!=1:raise ValueError(name+' did not complete its checked assertion')
        if sentinel.read_text().strip()!=nonce:raise ValueError(name+' real R sentinel missing')
        actual=identities(report['findings'])
        if actual!=oracle['findings']:raise ValueError(name+' exact finding mismatch')
        fixtures.append({'fixture':name,'engine':'R','source_hash':hashlib.sha256((pkg/'README.md').read_bytes()).hexdigest(),'expected_assertion_ids':oracle['assertion_ids'],'observed_assertion_ids':[s['id'] for s in _docexamples.extract(pkg/'README.md')[0] if s['expected']],'sentinel':nonce,'expected_findings':oracle['findings'],'actual_findings':actual})
    for name,missing in (('site-clean',False),('site-planted',True)):
        pkg=directory/name;package(pkg,'Fixture\n')
        (pkg/'man').mkdir();(pkg/'man'/'private.Rd').write_text('private\n')
        (pkg/'vignettes').mkdir();(pkg/'vignettes'/'foo.Rmd').write_text('# Fixture\n')
        for args in (['init','-b','main'],['config','user.email','fixture@example.org'],['config','user.name','Fixture'],['add','.'],['commit','-m','fixture']):
            subprocess.run(['git',*args],cwd=pkg,capture_output=True,check=True)
        requests=[]
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append(self.path)
                base=f'http://127.0.0.1:{self.server.server_port}/pkg/'
                routes=['articles/foo.html']+([] if missing else ['reference/private.html'])
                xml='<urlset>'+''.join('<url><loc>'+base+r+'</loc></url>' for r in routes)+'</urlset>'
                self.send_response(200);self.end_headers();self.wfile.write(xml.encode())
            def log_message(self,*args):pass
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:report=_docsite.audit(pkg,url=f'http://127.0.0.1:{server.server_port}/pkg/',ref='main')
        finally:server.shutdown();server.server_close();thread.join()
        oracle=expected['fixtures'][name];actual=identities(report['findings'])
        routes=sorted(_docsite.routes(['man/private.Rd','vignettes/foo.Rmd'],{})[0])
        if report['state']!='complete' or report['counts']['checked']!=len(routes) or actual!=oracle['findings'] or requests!=['/pkg/sitemap.xml']:
            raise ValueError(name+' actual HTTP fixture oracle mismatch')
        fixtures.append({'fixture':name,'engine':'HTTP','source_hash':hashlib.sha256((pkg/'man/private.Rd').read_bytes()+(pkg/'vignettes/foo.Rmd').read_bytes()).hexdigest(),'expected_routes':oracle['routes'],'observed_routes':routes,'sentinel':requests,'expected_findings':oracle['findings'],'actual_findings':actual})
    return {'fixture_executions':fixtures,'reported_r_checked':2,'reported_http_checked':4}


if __name__=='__main__':
    with tempfile.TemporaryDirectory(prefix='a2-oracles-') as temporary:
        print(json.dumps(collect(Path(temporary))))
