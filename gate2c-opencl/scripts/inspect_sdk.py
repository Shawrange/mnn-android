from pathlib import Path
import os,json
r=Path('/mnt/e/DUANCE/gate2c-opencl');s=Path('/home/shawrange/src/MNN-3.6.2')
out={}
for n in ['QNN_SDK_ROOT','QNN_ROOT','HEXAGON_SDK_ROOT']:
    v=os.environ.get(n);out[n]={'configured_value':v,'path_exists':Path(v).is_dir() if v else False}
    if v:out[n]['include_qnn_interface_exists']=(Path(v)/'include/QNN/QnnInterface.h').is_file()
out['default_hexagon_custom_outputs_exists']=(s/'source/backend/hexagon/htp-ops-lib/outputs').exists()
out['boundary']='Only configured locations and default output directory checked; no filesystem-wide absence claim, no download/build/run of NPU libraries.'
(r/'evidence/npu-static/sdk-state.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
