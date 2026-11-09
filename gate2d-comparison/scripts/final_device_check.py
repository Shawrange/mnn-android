"""One final read-only hash check, no model execution."""
from run import *
dep=load(R/'deployment.json');d=R/'evidence/final-device-check';d.mkdir();r=Runner(C,d)
out,_,rec=r.shell('hashes','sha256sum '+' '.join(dep['hashes']),d,90);must(rec)
actual={x.split()[1]:x.split()[0] for x in out.decode().splitlines()};assert actual==dep['hashes']
save(d/'verified.json',{'checked_at_utc':utc(),'all_original_assets_unchanged':True,'sha256':actual})
print('Final device hashes verified; no further inference')
