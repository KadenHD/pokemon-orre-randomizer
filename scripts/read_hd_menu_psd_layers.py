"""Bounded private PSD v1 RGB8 layer extractor, no changes to author sources."""
from pathlib import Path
import hashlib, json, struct, zlib
from PIL import Image

def layers(path):
    data=Path(path).read_bytes()
    if len(data)>64*1024*1024:
        raise ValueError('PSD exceeds private bounded input')
    sig,version,_,channels,height,width,depth,mode=struct.unpack_from('>4sH6sHIIHH',data)
    if (sig,version,depth,mode)!=(b'8BPS',1,8,3) or width*height>16*1024*1024:
        raise ValueError('Only bounded v1 RGB8 PSDs are supported')
    def u32(o):return struct.unpack_from('>I',data,o)[0]
    offset=26
    for _ in range(2):offset+=4+u32(offset)
    outer_end=offset+4+u32(offset);offset+=4
    layer_end=offset+4+u32(offset);offset+=4
    assert layer_end<=outer_end<=len(data)
    count=abs(struct.unpack_from('>h',data,offset)[0]);offset+=2
    assert count<=128
    records=[]
    for index in range(count):
        top,left,bottom,right,n=struct.unpack_from('>iiiiH',data,offset);offset+=18
        assert 0<right-left<=4096 and 0<bottom-top<=4096 and n<=8
        channel=[]
        for _ in range(n):
            cid,length=struct.unpack_from('>hI',data,offset);offset+=6;channel.append((cid,length))
        signature,blend,opacity,clipping,flags,_=struct.unpack_from('>4s4sBBBB',data,offset);offset+=12
        assert signature==b'8BIM'
        end=offset+4+u32(offset);offset+=4;extra=data[offset:end];q=offset
        for _ in range(2):q+=4+u32(q)
        name=data[q+1:q+1+data[q]].decode('latin1')
        records.append({'index':index,'name':name,'bounds':[left,top,right,bottom],
            'channels':channel,'blend':blend.decode('ascii'),'opacity':opacity,'flags':flags,
            'text_engine_data':b'TySh'in extra})
        offset=end
    for record in records:
        left,top,right,bottom=record['bounds'];w=right-left;h=bottom-top;decoded={}
        for cid,length in record['channels']:
            block=data[offset:offset+length];offset+=length
            assert len(block)==length and offset<=layer_end
            compression=struct.unpack_from('>H',block)[0]
            if compression==0:raw=block[2:]
            elif compression==1:
                sizes=struct.unpack_from('>'+str(h)+'H',block,2);pos=2+h*2;rows=[]
                for size in sizes:
                    row=block[pos:pos+size];pos+=size;out=bytearray();i=0
                    while i<len(row):
                        control=row[i];i+=1
                        if control<128:
                            n=control+1;out.extend(row[i:i+n]);i+=n
                        elif control>128:
                            out.extend(row[i:i+1]*(257-control));i+=1
                    assert len(out)==w
                    rows.append(out)
                assert pos==len(block)
                raw=b''.join(rows)
            elif compression==2:raw=zlib.decompress(block[2:])
            else:raise ValueError('Unsupported PSD compression')
            assert len(raw)==w*h
            decoded[cid]=Image.frombytes('L',(w,h),raw)
        assert all(c in decoded for c in (0,1,2))
        record['image']=Image.merge('RGBA',tuple(decoded[c]for c in (0,1,2))+(decoded.get(-1,Image.new('L',(w,h),255)),))
    return (width,height),records

if __name__=='__main__':
    source=Path('build/hd-deep-audit/hud/author-vectors/Pokemon XD UI SVGs V1.0/edited/tex1_454x78_497c305f6e96e421_02e3189f673c8fc2_9.psd')
    size,records=layers(source);out=Path(__file__).parent/'psd-layers';out.mkdir(exist_ok=False)
    for record in records:
        image=record.pop('image');target=out/f"layer-{record['index']:02d}.png";image.save(target)
        record.update(file=target.name,sha256=hashlib.sha256(target.read_bytes()).hexdigest())
    (out/'layers.json').write_text(json.dumps({'source':source.name,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'dimensions':size,'layers':records},indent=2)+'\n',encoding='utf-8')
