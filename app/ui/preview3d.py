"""结构 v2 → 自研轻量 3D 预览（canvas 软渲染，无外部 CDN 依赖）。

对照 crogen/CrochetPARADE 的"逐行 → 即时 3D"思路：instances 的归一化
位置/旋转 + 部件尺寸 → 三角面片 + 画家算法 + Lambert 着色。这是示意性
结构预览，不是物理仿真；y 按全高、x/z 同尺度缩放为简化假设。保持零
外部依赖（不引 three.js CDN）以维持应用的离线/隐私立场。
"""
from __future__ import annotations

import json
from typing import Any

# 单色部件的占位色（skin/body 不是毛线色名）→ 中性示意色
_PLACEHOLDER_HEX = {"skin": "#e8bfa8", "body": "#9aa7b8"}


def _hex_by_name(result: dict) -> dict[str, str]:
    """params 部件名 → 毛线色 hex（结构层的 color 字段可能还是占位符）。"""
    from app.models.colors import YARN_COLORS

    hex_by_name: dict[str, str] = {}
    for pp in (result.get("params") or {}).get("parts", []):
        pd = pp if isinstance(pp, dict) else (
            pp.model_dump() if hasattr(pp, "model_dump") else {})
        color = str(pd.get("color", ""))
        for (r, g, b), name in YARN_COLORS:
            if name == color:
                hex_by_name[str(pd.get("name"))] = f"#{r:02x}{g:02x}{b:02x}"
                break
        else:
            if color in _PLACEHOLDER_HEX:
                hex_by_name[str(pd.get("name"))] = _PLACEHOLDER_HEX[color]
    return hex_by_name


def build_payload(result: dict) -> dict[str, Any] | None:
    """result dict → 3D 预览数据；无可渲染实体时返回 None。"""
    structure = result.get("structure") or {}
    sparts = structure.get("parts") or []
    if not sparts:
        return None
    analysis = result.get("analysis") or {}
    height = float(analysis.get("height_cm") or 18.0)
    gauge = result.get("gauge") or {}
    stitch_w = 10.0 / max(float(gauge.get("stitches_per_10cm", 13.0)), 1e-6)
    row_h = 10.0 / max(float(gauge.get("rows_per_10cm", 16.0)), 1e-6)

    hex_by_name = _hex_by_name(result)
    rounds_by_name: dict[str, list] = {}
    for pp in (result.get("params") or {}).get("parts", []):
        pd = pp if isinstance(pp, dict) else (
            pp.model_dump() if hasattr(pp, "model_dump") else {})
        rounds_by_name[str(pd.get("name"))] = pd.get("rounds") or []

    items: list[dict[str, Any]] = []
    for part in sparts:
        name = str(part.get("name", "?"))
        shape = part.get("shape")
        entry: dict[str, Any] = {
            "name": name,
            "color": hex_by_name.get(name, "#c9a68a"),
            "shape": shape,
            "instances": [],
        }
        if shape == "profile":
            rounds = rounds_by_name.get(name) or []
            if not rounds:
                continue
            entry["lathe"] = {
                # 逐圈针数 → 半径（r = N·针宽 / 2π），与环形圈数图同口径
                "radii": [max(0.15, int(r.get("stitches", 0)) * stitch_w
                              / (2 * 3.14159265)) for r in rounds],
                "row_h": row_h,
            }
        else:
            diameter = float(part.get("diameter_cm") or 0)
            if diameter <= 0:
                # 圆柱/杯形部件的直径未存于结构层（由针数推导）：
                # r = N_max·针宽 / 2π，与环形圈数图同口径
                rounds = rounds_by_name.get(name) or []
                max_st = max((int(r.get("stitches", 0)) for r in rounds),
                             default=0)
                diameter = max_st * stitch_w / 3.14159265
            part_height = float(part.get("height_cm")
                                or part.get("length_cm") or 0)
            if shape == "sphere":
                part_height = diameter  # 球体高即直径
            if diameter <= 0 or part_height <= 0:
                continue
            entry["dims"] = {"r": diameter / 2.0, "h": part_height}
        for inst in part.get("instances", []):
            pos = inst.get("position") or {}
            rot = inst.get("rotation_deg") or {}
            entry["instances"].append({
                "p": [float(pos.get("x", 0)) * height,
                      float(pos.get("y", 0)) * height,
                      float(pos.get("z", 0)) * height],
                "r": [float(rot.get("x", 0)), float(rot.get("y", 0)),
                      float(rot.get("z", 0))],
            })
        if entry["instances"]:
            items.append(entry)
    if not items:
        return None
    return {"height": height, "items": items}


_JS = r"""
var DATA=__PAYLOAD__;
var cv=document.getElementById('c2p3d');
var ctx=cv.getContext('2d');
var yaw=0.6,pitch=0.35,zoom=1.0,drag=null;
function resize(){var r=cv.getBoundingClientRect();
  cv.width=Math.max(1,r.width*devicePixelRatio);
  cv.height=Math.max(1,r.height*devicePixelRatio);}
window.addEventListener('resize',function(){resize();draw();});
cv.addEventListener('mousedown',function(e){drag=[e.clientX,e.clientY];cv.style.cursor='grabbing';});
window.addEventListener('mouseup',function(){drag=null;cv.style.cursor='grab';});
window.addEventListener('mousemove',function(e){if(!drag)return;
  yaw+=(e.clientX-drag[0])*0.01;pitch+=(e.clientY-drag[1])*0.01;
  pitch=Math.max(-1.4,Math.min(1.4,pitch));drag=[e.clientX,e.clientY];draw();});
cv.addEventListener('wheel',function(e){e.preventDefault();
  zoom*=e.deltaY<0?1.1:0.9;zoom=Math.max(0.4,Math.min(3,zoom));draw();},{passive:false});
function rotY(a,x,z){var c=Math.cos(a),s=Math.sin(a);return [x*c+z*s,-x*s+z*c];}
function rotX(a,y,z){var c=Math.cos(a),s=Math.sin(a);return [y*c-z*s,y*s+z*c];}
function hx(h){return [parseInt(h.slice(1,3),16),parseInt(h.slice(3,5),16),parseInt(h.slice(5,7),16)];}
function meshSphere(r,seg,ring){var vs=[],fs=[];
  for(var i=0;i<=ring;i++){var phi=Math.PI*i/ring;
    for(var j=0;j<=seg;j++){var th=2*Math.PI*j/seg;
      vs.push([r*Math.sin(phi)*Math.cos(th),r*Math.cos(phi),r*Math.sin(phi)*Math.sin(th)]);}}
  for(i=0;i<ring;i++)for(var j2=0;j2<seg;j2++){var a=i*(seg+1)+j2,b=a+seg+1;
    fs.push([a,b,a+1]);fs.push([b,b+1,a+1]);}
  return {v:vs,f:fs};}
function meshCyl(r,h,seg,openTop){var vs=[],fs=[];
  for(var i=0;i<2;i++){var y=i?-h/2:h/2;
    for(var j=0;j<=seg;j++){var th=2*Math.PI*j/seg;
      vs.push([r*Math.cos(th),y,r*Math.sin(th)]);}}
  for(var j3=0;j3<seg;j3++){var a=j3,b=seg+1+j3;
    fs.push([a,b,a+1]);fs.push([b,b+1,a+1]);}
  var apexTop=vs.length;vs.push([0,h/2,0]);
  var apexBot=vs.length;vs.push([0,-h/2,0]);
  for(var j4=0;j4<seg;j4++){
    if(!openTop)fs.push([apexTop,j4+1,j4]);
    fs.push([apexBot,j4+seg+2,j4+seg+1]);}
  return {v:vs,f:fs};}
function meshLathe(rad,rowH,seg){var vs=[],fs=[],n=rad.length,h=n*rowH;
  for(var i=0;i<n;i++){var y=h/2-i*rowH;
    for(var j=0;j<=seg;j++){var th=2*Math.PI*j/seg;
      vs.push([rad[i]*Math.cos(th),y,rad[i]*Math.sin(th)]);}}
  for(i=0;i<n-1;i++)for(var j5=0;j5<seg;j5++){var a2=i*(seg+1)+j5,b2=a2+seg+1;
    fs.push([a2,b2,a2+1]);fs.push([b2,b2+1,a2+1]);}
  var c0=[],cs=[];for(var j6=0;j6<=seg;j6++){c0.push(j6);cs.push((n-1)*(seg+1)+j6);}
  var apexTop=vs.length;vs.push([0,h/2,0]);
  var apexBot=vs.length;vs.push([0,h/2-h,0]);
  for(var j7=0;j7<seg;j7++){fs.push([apexTop,c0[j7+1],c0[j7]]);
    fs.push([apexBot,cs[j7],cs[j7+1]]);}
  return {v:vs,f:fs};}
function shade(base,nx,ny,nz){var L=[0.4,0.7,-0.6];
  var d=Math.max(0,nx*L[0]+ny*L[1]+nz*L[2]);var k=0.55+0.45*d;
  return 'rgb('+Math.round(base[0]*k)+','+Math.round(base[1]*k)+','+Math.round(base[2]*k)+')';}
function draw(){resize();var W=cv.width,H2=cv.height;
  ctx.clearRect(0,0,W,H2);var faces=[];
  var D=60/zoom,f=2.2*D;
  DATA.items.forEach(function(item){var rgb=hx(item.color);var m=null;
    if(item.shape==='sphere'){m=meshSphere(Math.max(item.dims.r,0.4),12,8);}
    else if(item.shape==='cup'){m=meshCyl(Math.max(item.dims.r,0.4),item.dims.h,12,true);}
    else if(item.shape==='cylinder'){m=meshCyl(Math.max(item.dims.r,0.4),item.dims.h,12,false);}
    else if(item.lathe){m=meshLathe(item.lathe.radii,item.lathe.row_h,12);}
    if(!m)return;
    item.instances.forEach(function(inst){
      var rz=(inst.r[2]||0)*Math.PI/180,rx=(inst.r[0]||0)*Math.PI/180;
      var cz=Math.cos(rz),sz=Math.sin(rz),cx=Math.cos(rx),sx=Math.sin(rx);
      var wp=m.v.map(function(v){
        var x1=v[0]*cz-v[1]*sz,y1=v[0]*sz+v[1]*cz,z1=v[2];
        var y2=y1*cx-z1*sx,z2=y1*sx+z1*cx;
        var wx=x1+inst.p[0],wy=y2+inst.p[1],wz=z2+inst.p[2];
        var v1=rotY(yaw,wx,wz);
        var v2=rotX(pitch,v1[1],v1[0]);
        return {vx:v1[0],vy:v2[0],vz:v2[1],wx:wx,wy:wy,wz:wz};});
      m.f.forEach(function(tri){
        var A=wp[tri[0]],B=wp[tri[1]],C=wp[tri[2]];
        var ax=B.wx-A.wx,ay=B.wy-A.wy,az=B.wz-A.wz;
        var bx=C.wx-A.wx,by=C.wy-A.wy,bz=C.wz-A.wz;
        var nx=ay*bz-az*by,ny=az*bx-ax*bz,nz=ax*by-ay*bx;
        var nl=Math.hypot(nx,ny,nz)||1;nx/=nl;ny/=nl;nz/=nl;
        var vz=(A.vz+B.vz+C.vz)/3;
        var sc=f/Math.max(4,D+vz);
        faces.push({z:vz,
          pts:[[W/2+A.vx*sc,H2/2-A.vy*sc],
               [W/2+B.vx*sc,H2/2-B.vy*sc],
               [W/2+C.vx*sc,H2/2-C.vy*sc]],
          rgb:rgb,nx:nx,ny:ny,nz:nz});});});});
  faces.sort(function(a,b){return b.z-a.z;});
  faces.forEach(function(fc){ctx.beginPath();
    ctx.moveTo(fc.pts[0][0],fc.pts[0][1]);
    ctx.lineTo(fc.pts[1][0],fc.pts[1][1]);
    ctx.lineTo(fc.pts[2][0],fc.pts[2][1]);ctx.closePath();
    ctx.fillStyle=shade(fc.rgb,Math.abs(fc.nx),Math.abs(fc.ny),Math.abs(fc.nz));
    ctx.fill();ctx.strokeStyle='rgba(0,0,0,0.06)';ctx.lineWidth=0.5;ctx.stroke();});
  ctx.fillStyle='#543f35';ctx.font=(11*devicePixelRatio)+'px sans-serif';
  ctx.fillText('示意预览——拖动旋转，滚轮缩放（非物理仿真）',
    8*devicePixelRatio,16*devicePixelRatio);}
setTimeout(function(){resize();draw();},50);
"""


def structure_preview_html(result: dict) -> str | None:
    """结构 v2 → 可嵌入 st.html 的预览 HTML；无可渲染实体时返回 None。"""
    payload = build_payload(result)
    if payload is None:
        return None
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    canvas = ('<canvas id="c2p3d" style="width:100%;height:100%;display:block;'
              'background:#fffdf8;border-radius:8px;cursor:grab;"></canvas>')
    return canvas + "<script>" + _JS.replace("__PAYLOAD__", data) + "</script>"
