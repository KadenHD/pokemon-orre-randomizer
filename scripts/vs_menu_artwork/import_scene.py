"""Import the exact six identified source models without identity renders."""

import os
import os
import runpy
import sys
from pathlib import Path

os.environ['VS_IMPORT_ONLY']='1'
sys.argv=['import_scene.py','--','rinto_0100','trainer_f_0100','gba_fl_f_0100',
          'gba_fl_m_0100','gba_emr_f_0100','gba_emr_m_0100']
runpy.run_path(str(Path(__file__).with_name('probe_blender.py')),run_name='__main__')
