__all__ = ['svg']
import networkx as nx
import svgwrite as sw
from svgwrite.path import Path
from svgwrite.shapes import Rect, Line, Polygon
from svgwrite.text import Text, TextPath, TSpan
from svgwrite.container import Marker, Group
from svgwrite import Drawing
from sys import stderr
import math
#estimated fontsize
GlobalScale = 1000.
Padding = 0.01
FontSize = 20.
LineWidth = '2px'
LineSpacing = 2.
def get_size(labeltxt):
    lines = labeltxt.split('\n')
    tw = max([len(line) for line in lines])
    th = len(lines)
    width = tw * FontSize / GlobalScale
    height = th * FontSize / GlobalScale * LineSpacing
    return width, height

def get_anchor(pos, otherpos):
    anchors = [
            (1.0, 0.5),
            (0.5, 0.0),
            (0., 0.5),
            (0.5, 1.0)]
    diff = (otherpos[0] - pos[0], otherpos[1] - pos[1])
    # the svg coordinate has wrong handness
    ang = math.atan2(-diff[1], diff[0])
    ang = int(ang / math.pi * 180)
    ang += 45
    if ang < 0:
        ang += 360
    if ang >= 360:
        ang -= 360
    phase = ang // 90
    #print pos, otherpos, ang, phase, anchors[phase]
    return anchors[phase]
def scale(v):
    return v[0] * GlobalScale, v[1] * GlobalScale
def clip(v, s):
    def f(a, b):
        if a + b > 1.0 - Padding:
            return 1.0 - Padding - b
        if a < Padding:
            return Padding
        return a
    return tuple([f(a, b) for a, b in zip(v, s)])

def MultiLineText(s, **kwargs):
    dy = kwargs.pop('dy', LineSpacing * FontSize)
    x, y = kwargs.pop('insert', (0, 0))
    lines = s.split('\n')
    txt = Text('', insert=(x, y - 0.5 * dy * (len(lines) + 1)), **kwargs)
    for i, line in enumerate(lines):
        if len(line) > 0:
            ts = TSpan(line, x=[x], dy=[dy], **kwargs)
            txt.add(ts)
    return txt

def DefaultNodeFormatter(node, data):
    return 'Node[%d]\nABCDEF\n' % node, {}
def DefaultEdgeFormatter(u, v, data):
    return 'Edge[%d, %d]' % (u, v), {}

def svg(g, pos, nodeformatter=DefaultNodeFormatter, edgeformatter=DefaultEdgeFormatter):
    """ formatter returns a string and a dict of the attributes(undefined yet)"""
    dwg = Drawing(size=('400px', '400px'), profile='basic', version=1.2)
    dwg.viewbox(minx=0, miny=0, width=GlobalScale, height=GlobalScale)

    # now add the marker
    marker = Marker(orient='auto', markerUnits="strokeWidth", size=(20, 20), refX=1.0, refY=0.5)
    marker.viewbox(minx=0, miny=0, width=1, height=1)
    marker.add(Polygon(points=[(0, 0.2), (1, 0.5), (0, 0.8)], fill='black', stroke='none'))
    dwg.defs.add(marker)

    pos = pos.copy()
    x = []
    y = []
    size = {}

    for node, data in g.nodes_iter(data=True):
        p = pos[node]
        label, prop = nodeformatter(node, data)
        size[node] = get_size(label)
        x.append(p[0])
        y.append(p[1])

    xmin = min(x)
    xmax = max(x)
    ymin = min(y)
    ymax = max(y)

    # normalize input pos to 0 ~ 1
    for node in g.nodes_iter():
        p = pos[node]
        p = ((p[0] - xmin) / (xmax - xmin),
             (p[1] - ymin) / (ymax - ymin) )

        wh = size[node]
        p = clip(p, wh)
        pos[node] = p

    # draw the nodes
    for node, data in g.nodes_iter(data=True):
        label, prop = nodeformatter(node, data)
        p = pos[node]
        wh = size[node]
        wh, p = scale(wh), scale(p)
        grp = Group()
        ele = Rect(insert=p, size=wh, 
                stroke_width=LineWidth,
                stroke='black',
                fill='none',
                rx=FontSize,
                ry=FontSize,
                )
        grp.add(ele)
        txtp = p[0] + wh[0] * 0.5, p[1] + wh[1] * 0.7

        txt = MultiLineText(label, insert=txtp, 
                font_family='monospace', font_size=FontSize, 
                text_anchor="middle")

        grp.add(txt)
        dwg.add(grp)

    # draw the edges
    for u, v, data in g.edges_iter(data=True):
        label, prop = edgeformatter(u, v, data)
        p1 = pos[u]
        p2 = pos[v]
        a = get_anchor(p1, p2)
        #stderr.write("%s %s %s\n" % (str(p1), str(p2), str(a)))
        p1 = p1[0] + size[u][0] * a[0], p1[1] + size[u][1] * a[1]
        a = get_anchor(p2, p1)
        p2 = p2[0] + size[v][0] * a[0], p2[1] + size[v][1] * a[1]
        p1 = p1[0], p1[1]
        p2 = p2[0], p2[1]
        p1 = scale(p1)
        p2 = scale(p2)
        txtp = (p1[0] + p2[0]) * 0.5, (p1[1] + p2[1]) * 0.5

        grp = Group()
        edge = Path(d=[('M', p1[0], p1[1]), (p2[0], p2[1])], 
                marker_end=marker.get_funciri(), 
                stroke_width=LineWidth, 
                stroke='black')
        grp.add(edge)
        txt = Text(label, 
                font_size=FontSize, 
                font_family='monospace', 
                text_anchor="middle",
                insert=txtp, 
                )
        txt.rotate(180. / math.pi * math.atan2((p2[1] - p1[1]), p2[0] - p1[0]) + 180,
                center=txtp)
        txt.translate(tx=0, ty=-FontSize * 0.5)
        #txtpath = TextPath(edge.get_funciri(), label, 
        #        startOffset="50%",
        #        )
        #txt.add(txtpath)
        grp.add(txt)
        dwg.add(grp)
    return dwg.tostring()

def test():
    g = nx.DiGraph()

    g.add_star(range(4))
    g.add_cycle(range(4))
    #pos = nx.spring_layout(g)
    pos = nx.shell_layout(g)
    
    print svg(g, pos)

    get_anchor((0, 0), (1, 0))
    get_anchor((0, 0), (1, 1))
    get_anchor((0, 0), (0, 1))
    get_anchor((0, 0), (-1, 1))
    get_anchor((0, 0), (-1, 0))
    get_anchor((0, 0), (-1, -1))
    get_anchor((0, 0), (0, -1))
    get_anchor((0, 0), (1, -1))
if __name__ == "__main__":
    test()
