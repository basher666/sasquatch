import os
import sys


import time
import numpy as np
import scipy
import scipy.misc
import matplotlib.pyplot as plt
import pylab
import re
from parser_utilities import *
import math


BACKGROUND = 245 # arbitrary
BORDERCOLOR = 0 # not arbitrary, this is the border color of the pictures
WHITE = 255 # also not arbitrary


# remove anything smaller than this that is in contact with anything bigger than this
tiny_threshold = 50

# how different two things can be and still count is rescaled versions
rescale_threshold = 3.06


class Shape():
    def __init__(self,mask):
        self.initialize(mask)
    def initialize(self,mask):
        self.mask = mask
        self.mass = np.sum(mask)
        self.contains = []
        self.borders = []
        self.merge_borders = []
        self.name = None
        self.scale = 1.0
        
        self.outline = mask_outline(mask)
        
        self.x,self.y,self.centered = center_mask(mask,self.mass)
        
    def same_shape(self,other):
        d = np.logical_xor(self.centered,other.centered)
        d = np.sum(d)
        return d < 10
    def rescaled_shape(self,other):
        if self.mass > other.mass:
            return other.rescaled_shape(self)
        f = math.sqrt(float(self.mass) / float(other.mass))
        o = scale_mask(other.centered,f)
        differences = min([ np.sum(np.logical_xor(self.centered,n))
                            for n in neighbor_matrices(o) ])
        r = float(differences)/math.sqrt(self.mass)
        return r < rescale_threshold
    def contains_other(self,other):
        return mask_subset(other.mask,self.mask)
    def touches(self,other):
        return mask_overlap(self.outline, other.mask) or mask_overlap(other.outline, self.mask)
    def merge_with(self,other):
        new_mask = np.logical_or(self.mask,other.mask)
        self.initialize(new_mask)





# claims any borders that are both touching the shape and the background
def claim_borders(i,s):
    n1,n2,n3,n4 = neighbor_matrices(i)
    touches_background = np.logical_or.reduce((n1 == BACKGROUND,
                                               n2 == BACKGROUND,
                                               n3 == BACKGROUND,
                                               n4 == BACKGROUND))
    touches_shape = np.logical_or.reduce((n1 == s,
                                          n2 == s,
                                          n3 == s,
                                          n4 == s))
    is_border = i == BORDERCOLOR
    claim = np.logical_and.reduce((touches_background,touches_shape,is_border))
    return i*(1-claim) + s*claim

def fill_center(mask):
    mask = mask*42
    fill(mask,0,0,0,99)
    return 1 - (mask == 99)
    
def connected_components(i):
    w = i.shape[0]
    h = i.shape[1]
    ns = 1 # next shape
    shapes = []
    fill(i,0,0,WHITE,BACKGROUND)
    for x in range(w):
        for y in range(h):
            if i[x,y] == WHITE:
                fill(i,x,y,WHITE,ns)
                # claim borders that touched the background
                i = claim_borders(i,ns)
                #view(fill_center(i == ns))
                #view(255*fill_center(i == ns))
                shapes.append(fill_center(i == ns))
                i = replace(i,ns,BACKGROUND)
                #view(i)
                ns += 1

    # plop all the shapes down
    for j in range(len(shapes)):
        s = shapes[j]
        i = i*(1-s) + s*(j+1)

    i = replace(i,BACKGROUND,-1)
    if False:
        cs = [center_mask(s)[2]     for s in shapes]
        view(cs[1])
        view(cs[3])
        view(np.logical_xor(cs[1],cs[3]))

    # claim remaining borders
    modified = True
    while modified:
        modified = False
        for x in range(1,w-1):
            for y in range(1,h-1):
                if i[x,y] == 0:
                    new = max(i[x-1,y],
                              i[x+1,y],
                              i[x,y-1],
                              i[x,y+1])
                    if new != 0:
                        modified = True
                        i[x,y] = new
        if not modified:
            for x in range(1,w-1):
                for y in range(1,h-1):
                    if i[x,y] == 0:
                        # try diagonals
                        new = max(i[x-1,y-1],
                                  i[x-1,y+1],
                                  i[x+1,y-1],
                                  i[x+1,y+1])
                        if new != 0:
                            modified = True
                            i[x,y] = new
    # pull the shapes out of the picture again
    for j in range(len(shapes)):
        shapes[j] = fill_center(i == (j+1))
    
    i = replace(i,-1,BACKGROUND)
    if False:
        view(i*30)
    artifact = {}
    background_mask = i == BACKGROUND
    for j,s in enumerate(shapes):
        # see this touching the background
        n1,n2,n3,n4 = neighbor_matrices(s)
        n = np.logical_or.reduce((n1,n2,n3,n4))
        if mask_overlap(background_mask,n):
            artifact[j] = False
        else:
            # see if this is contained in something else
            for jp in range(len(shapes)):
                if j != jp and mask_subset(s,shapes[jp]):
                    artifact[j] = False
                    break
            artifact[j] = artifact.get(j,True)
    if False: # display only those that aren't artifacts
        i[:] = BACKGROUND
        for j,s in enumerate(shapes):
            if not artifact[j]:
                i = i*(1-s) + (j+2)*s
        view(i*50)
    return [Shape(s) for j,s in enumerate(shapes) if not artifact[j] ]




# resets all of the qualitative information
def compute_qualitative(shapes):
    for s in shapes:
        s.contains = []
        s.borders = []
    for s in shapes:
        for z in shapes:
            if s == z: continue
            if s.contains_other(z):
                s.contains.append(z)
    for s in shapes:
        for z in shapes:
            if s == z or s in z.contains or z in s.contains: continue
            if s.touches(z):
                s.borders.append(z)
        

def analyze(filename):
    i = scipy.misc.imread(filename,1)
    i = i.astype(np.int32)
    shapes = connected_components(i)

    # merger artifacts with what they came from
    changed = True
    while changed:
        changed = False
        compute_qualitative(shapes)
        to_remove = None
        for s,z in [(s,z) for s in shapes for z in shapes ]:
            if s == z: continue
            if z.mass < tiny_threshold and s.mass >= z.mass and z in s.borders:
                s.merge_with(z)
                to_remove = z
                break
        if to_remove:
            changed = True
            shapes.remove(to_remove)
    if False:
        i[:] = WHITE
        for j,s in enumerate(shapes):
            s = s.mask
            i = i*(1-s) + (j+2)*s
        view(i*30)

    ns = len(shapes)

    # equivalence classes of identical shapes
    identical = {}
    for s in shapes:
        new_class = True
        for j,k in identical.items():
            if new_class:
                for sp in k:
                    if s.same_shape(sp):
                        k.append(s)
                        new_class = False
                        break
        if new_class:
            identical[len(identical)] = [s]
    equivalent_mass = {}
    for j,k in identical.items():
        equivalent_mass[j] = float(sum([s.mass for s in k ]))/len(k)

    next_label = 1
    for i,ki in identical.items():
        i_name = None
        for j in range(i):
            # is class i a rescaling of class j?
            rescaling = any([ s.rescaled_shape(sp) 
                              for s in ki
                              for sp in identical[j] ])
            if rescaling:
                # take their name
                i_name = identical[j][0].name
                ratio = equivalent_mass[i]/equivalent_mass[j]
                if ratio < 1.0:
                    for s in ki: s.scale = ratio
                else:
                    for s in identical[j]: s.scale = 1.0/ratio
                break
        if i_name == None:
            i_name = next_label
            next_label += 1
        for s in ki:
            s.name = i_name
    # build output string
    os = []
    for s in shapes:
        os.append("Shape(%i,%i,%i,%f)" % (s.x,s.y,s.name,s.scale))
    os = ','.join(os)
    os = os + "\n"
    for s in xrange(0,ns):
        for sp in xrange(0,ns):
            if shapes[sp] in shapes[s].contains:
                os = os + "contains(" + str(s) + ", " + str(sp) + ")\n"
    for s in xrange(0,ns):
        for sp in xrange(0,ns):
            if s < sp and shapes[sp] in shapes[s].borders:
                os = os + "borders(" + str(s) + ", " + str(sp) + ")\n"
    return os

    
sys.setrecursionlimit(128*128*2)

jobs = []

arguments = sys.argv[1:]
if len(arguments) == 0:
    arguments = [str(i) for i in range(1,24) ]
for argument in arguments:
    if argument.isdigit():
        argument = 'svrt/results_problem_%s' % argument
    if os.path.isdir(argument):
        for f in os.listdir(argument):
            if f.endswith(".png"):
                jobs = jobs + [argument + "/" + f]
    else:
        jobs = jobs + [argument]
for j in jobs:
    print j
    a = analyze(j)
    print a
    o = j[:-3]+"h"
    # useful special case
    m = re.match("svrt/results_problem_(\d+)/sample_(\d)_(\d+).png",j)
    if m:
        o = "pictures/%s_%s_%i" % (m.group(1),m.group(2),int(m.group(3)))
    with open(o,"w") as f:
        f.write(a)
    print ""


 

