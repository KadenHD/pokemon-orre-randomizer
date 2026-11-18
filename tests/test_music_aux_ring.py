"""Execute the shipped AUX patch fragment against impulse/wrap/reset inputs.

This small C harness needs a compiler, but no game assets, DLL or audio device.
The independent expected FIFO is the retail three-buffer/two-cycle ordering.
"""
import ctypes as C
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AuxRingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(); cls.addClassCleanup(cls.temp.cleanup)
        folder = Path(cls.temp.name)
        patches = json.loads((ROOT/'native/music/patches.json').read_text())
        changes = next(row for row in patches if row['path']=='src/musyx/runtime/hw_pc.c')['changes']
        change = next(row for row in changes if 'Retail consumes the AUX return' in row['after'])
        definitions = '''#include <stdint.h>
#include <string.h>
typedef int32_t s32; typedef uint32_t u32; typedef uint64_t u64;
#define SAL_SAMPLES_PER_FRAME 160
#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT
#endif
static void salPCConvertCycle(s32 *out,u32 n,u32 rate,u64 tick,const s32 *in,u32 frames,u32 oldrate,u64 oldtick,void *history) {
  (void)rate;(void)tick;(void)frames;(void)oldrate;(void)oldtick;(void)history;
  memcpy(out,in,n*sizeof(s32));
}
'''
        def function(name, fragment):
            return '''EXPORT void NAME(const s32 *input,u32 count,u32 rate,s32 *output) {
  s32 a[3][480]={{0}},b[3][480]={{0}};
  struct {s32 *auxA[3];s32 *auxB[3];} studio,*stp=&studio;
  for(u32 i=0;i<3;++i){studio.auxA[i]=a[i];studio.auxB[i]=b[i];}
  s32 legacyWork[3][160]={{0}},adaptedWork[3][160]={{0}};
  s32 effectHistory[1][2][2][3][4]={0};u32 st=0,bus=0,channel=0,cycleFrames=160;
  for(u32 cycle=0;cycle<count;++cycle){
    u32 salAuxFrame=cycle%3;u64 cycleTick=(u64)cycle*5;
    memset(a[salAuxFrame],0,sizeof(a[salAuxFrame]));
    for(u32 i=0;i<160;++i)a[salAuxFrame][i]=input[cycle];
    s32 *work=stp->auxA[(salAuxFrame+2)%3];
    for(u32 i=0;i<160;++i)legacyWork[0][i]=work[i]*2;
FRAGMENT
    output[cycle]=adaptedWork[0][0];
  }
}
'''.replace('NAME',name).replace('FRAGMENT',fragment)
        source = folder/'aux.c'; source.write_text(definitions+function('baseline',change['before'])+function('corrected',change['after']))
        if sys.platform=='win32':
            from scripts.build_music import build_environment
            try:
                compiler,environment = build_environment()
            except RuntimeError as error:
                raise unittest.SkipTest(str(error))
            library = folder/'aux.dll'
            command = [str(compiler),'/nologo','/LD','/O2','/MT',str(source),'/link','/OUT:'+str(library)]
        else:
            compiler = shutil.which('cc')
            if not compiler:
                raise unittest.SkipTest('C compiler unavailable for AUX fragment execution')
            environment = None; library = folder/'aux.so'
            command = [compiler,'-shared','-fPIC','-O2',str(source),'-o',str(library)]
        result = subprocess.run(command,cwd=folder,env=environment,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        if result.returncode:
            raise AssertionError(result.stdout)
        cls.library = C.CDLL(str(library))
        if sys.platform=='win32':
            from _ctypes import FreeLibrary
            # DLL must be unloaded before TemporaryDirectory removes its file.
            cls.addClassCleanup(FreeLibrary, cls.library._handle)
        for name in ('baseline','corrected'):
            getattr(cls.library,name).argtypes=[C.POINTER(C.c_int32),C.c_uint32,C.c_uint32,C.POINTER(C.c_int32)]
            getattr(cls.library,name).restype=None

    def trace(self, values, *, rate=32000, corrected=True):
        source=(C.c_int32*len(values))(*values); output=(C.c_int32*len(values))()
        getattr(self.library,'corrected' if corrected else 'baseline')(source,len(values),rate,output)
        return list(output)

    def test_impulse_matches_retail_two_cycle_return(self):
        self.assertEqual(self.trace([1000,0,0,0,0]),[0,0,2000,0,0])
        self.assertEqual(self.trace([1000,0,0,0,0],corrected=False),[0,2000,0,0,0])

    def test_wrap_and_reset_leave_no_previous_wet_samples(self):
        tags=[11,23,31,-7,19,41,53,-67,79]
        self.assertEqual(self.trace(tags),[0,0]+[2*value for value in tags[:-2]])
        self.assertEqual(self.trace([0]*9),[0]*9)

    def test_signed_return_and_non32k_branch(self):
        tags=[1000,-1000,3276,-3276,99,0]
        self.assertEqual(self.trace(tags),[0,0]+[2*value for value in tags[:-2]])
        self.assertEqual(self.trace(tags,rate=48000),self.trace(tags,rate=48000,corrected=False))


if __name__=='__main__':
    unittest.main()
