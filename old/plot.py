#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
plot.py
-------

'''

from __future__ import division, print_function, absolute_import, unicode_literals
import numpy as np
import matplotlib.pyplot as pl
import matplotlib.cm as cm
from matplotlib.colors import LinearSegmentedColormap, colorConverter
import subprocess
try:
  from PIL import Image
except:
  Image = None
from . import planet
from .transit import Transit, QUADRATIC, KIPPING, NONLINEAR, MAXPTS
from . import PSZGPATH
import sys

__all__ = ['PlotTransit', 'PlotImage', 'AnimateImage']

def I(r, limbdark):
  '''
  The standard quadratic limb darkening law.
  
  '''
  
  if limbdark.ldmodel == QUADRATIC:
    u1 = limbdark.u1
    u2 = limbdark.u2
    return (1-u1*(1-np.sqrt(1-r**2))-u2*(1-np.sqrt(1-r**2))**2)/(1-u1/3-u2/6)/np.pi
  elif limbdark.ldmodel == KIPPING:
    a = np.sqrt(limbdark.q1)
    b = 2*limbdark.q2
    u1 = a*b
    u2 = a*(1 - b)
    return (1-u1*(1-np.sqrt(1-r**2))-u2*(1-np.sqrt(1-r**2))**2)/(1-u1/3-u2/6)/np.pi
  elif limbdark.ldmodel == NONLINEAR:
    raise Exception('Nonlinear model not yet implemented!')                           # TODO!
  else:
    raise Exception('Invalid limb darkening model.')
  
def Star(ax, limbdark, x=0, y=0, r=1, n=100, color=(1.0, 0.85, 0.1), zorder=-1):
  '''
  
  '''
    
  # Ensure RGB
  color = colorConverter.to_rgb(color)
  
  # Create a simple gradient colormap (0 = center, bright; 1 = limb, dark)
  dictylbk = {'red':  ((0.0, color[0], color[0]),
                       (1.0, 0.0, 0.0)),

             'green': ((0.0, color[1], color[1]),
                       (1.0, 0.0, 0.0)),

             'blue':  ((0.0, color[2], color[2]),
                       (1.0, 0.0, 0.0))
             }
  cmap = LinearSegmentedColormap('YlBk', dictylbk)
  
  # Limb darkening profile
  rad = np.linspace(0,1,n)[::-1]
  Ir = I(rad,limbdark)/I(0,limbdark)
  for ri,Iri in zip(rad,Ir):
    lightness = 0.95*Iri  
    color = cmap(1 - lightness)
    star = pl.Circle((x, y), ri*r, color=color, alpha=1., zorder = zorder)
    ax.add_artist(star)

def Planet(ax, x = 0, y = 0, z = 0, r = 0.25, long0 = 0., image_map='earth'):
  '''
  
  '''
  
  p = planet.Planet(RpRs = r, image_map=image_map)
  p.gen_image(xyz = (x,y,z))
  p.plot_image(ax=ax, extent=(x-r,x+r,y-r,y+r), long0 = long0)

def Trail(ax, x, y, z, f, r = 0.05, color = "#4682b4", ndots = None, RpRs = 0.25):
  '''
  
  '''
  
  if ndots is None: 
    ndots = int(len(x)/2.)

  # x,y must span exactly one orbit
  for i in range(f - ndots, f):
    # Don't draw trails inside the planet
    if np.sqrt((x[i] - x[f])**2 + (y[i] - y[f])**2 + (z[i] - z[f])**2) <= 0.95*RpRs: 
      continue

    alpha = 0.2*((i - (f - ndots))/(1.*ndots))**2
    
    if z[i] < z[f]:
      if z[i] < 0:
        # In front of planet and star
        zorder = 3
      else:
        # In front of planet, behind star
        zorder = 1
    else:
      if z[i] < 0:
        # Behind planet, in front of star
        zorder = -1
      else:
        # Behind planet and star
        zorder = -3
    trail = pl.Circle((x[i], y[i]), r, color=color, zorder = zorder, alpha = alpha)
    ax.add_artist(trail)

def PlotTransit(compact = False, ldplot = True, plottitle = "", plotname = "transit", 
                xlim = None, binned = True, **kwargs):
  '''
    
  '''

  # Plotting
  fig = pl.figure()
  fig.set_size_inches(12,8)
  fig.subplots_adjust(hspace=0.3)
  ax1, ax2 = pl.subplot(211), pl.subplot(212)

  t0 = kwargs.pop('t0', 0.)
  trn = Transit(**kwargs)
  try:
    trn.Compute()
    notransit = False
  except Exception as e:
    if str(e) == "Object does not transit the star.":
      notransit = True
    else: raise Exception(e)

  time = trn.arrays.time + t0
  
  if not notransit:
    if binned:
      trn.Bin()
      flux = trn.arrays.bflx
    else:
      flux = trn.arrays.flux

    time = np.concatenate(([-1.e5], time, [1.e5]))                                    # Add baseline on each side
    flux = np.concatenate(([1.], flux, [1.]))
    ax1.plot(time, flux, '-', color='DarkBlue')
    rng = np.max(flux) - np.min(flux)
  
    if rng > 0:
      ax1.set_ylim(np.min(flux) - 0.1*rng, np.max(flux) + 0.1*rng)
      left = np.argmax(flux < (1. - 1.e-8))
      right = np.argmax(flux[left:] > (1. - 1.e-8)) + left
      rng = time[right] - time[left]        
      ax1.set_xlim(time[left] - rng, time[right] + rng)
  
  ax1.set_xlabel('Time (Days)', fontweight='bold')
  ax1.set_ylabel('Normalized Flux', fontweight='bold')

  # Adjust these for full-orbit plotting
  per = kwargs.get('per')
  kwargs.update({'fullorbit': True})
  kwargs.update({'exppts': 30})
  kwargs.update({'exp_time': 50 * per / MAXPTS})
  trn = Transit(**kwargs)
  
  try:
    trn.Compute()
  except Exception as e:
    if str(e) == "Object does not transit the star.":
      pass
    else: raise Exception(e)

  # Sky-projected motion
  x = trn.arrays.x
  y = trn.arrays.y
  z = trn.arrays.z
  inc = (np.arccos(trn.transit.bcirc/trn.transit.aRs)*180./np.pi)                     # Orbital inclination
  
  # Mask the star
  for j in range(len(x)):
    if (x[j]**2 + y[j]**2) < 1. and (z[j] > 0):
      x[j] = np.nan
      y[j] = np.nan
  
  # The star
  r = np.linspace(0,1,100)
  Ir = I(r,trn.limbdark)/I(0,trn.limbdark)
  
  for ri,Iri in zip(r[::-1],Ir[::-1]):
    star = pl.Circle((0, 0), ri, color=str(0.95*Iri), alpha=1.)
    ax2.add_artist(star)

  # Inset: Limb darkening
  if ldplot:
    if compact:
      inset1 = pl.axes([0.145, 0.32, .09, .1])
    else:
      inset1 = fig.add_axes([0.925,0.3,0.2,0.15])
    inset1.plot(r,Ir,'k-')
    pl.setp(inset1, xlim=(-0.1,1.1), ylim=(-0.1,1.1), xticks=[0,1], yticks=[0,1])
    for tick in inset1.xaxis.get_major_ticks() + inset1.yaxis.get_major_ticks():
      tick.label.set_fontsize(8)
    inset1.set_ylabel(r'I/I$_0$', fontsize=8, labelpad=-8)
    inset1.set_xlabel(r'r/R$_\star$', fontsize=8, labelpad=-8)
    inset1.set_title('Limb Darkening', fontweight='bold', fontsize=9)
    
  # Inset: Top view of orbit
  if compact:
    inset2 = pl.axes([0.135, 0.115, .1, .1])
  else:
    inset2 = fig.add_axes([0.925,0.1,0.2,0.15])
  pl.setp(inset2, xticks=[], yticks=[])
  trn.transit.bcirc = trn.transit.aRs                                                 # This ensures we are face-on
  try:
    trn.Compute()
  except Exception as e:
    if str(e) == "Object does not transit the star.":
      pass
    else: raise Exception(e)
  xp = trn.arrays.x
  yp = trn.arrays.y
  inset2.plot(xp, yp, '-', color='DarkBlue', alpha=0.5)
  # Draw some invisible dots at the corners to set the window size
  xmin, xmax, ymin, ymax = np.nanmin(xp), np.nanmax(xp), np.nanmin(yp), np.nanmax(yp)
  xrng = xmax - xmin
  yrng = ymax - ymin
  xmin -= 0.1*xrng; xmax += 0.1*xrng;
  ymin -= 0.1*yrng; ymax += 0.1*yrng;
  inset2.scatter([xmin,xmin,xmax,xmax], [ymin,ymax,ymin,ymax], alpha = 0.)
  # Plot the star
  for ri,Iri in zip(r[::-10],Ir[::-10]):
    star = pl.Circle((0, 0), ri, color=str(0.95*Iri), alpha=1.)
    inset2.add_artist(star)
  # Plot the planet
  ycenter = yp[np.where(np.abs(xp) == np.nanmin(np.abs(xp)))][0]
  while ycenter > 0:
    xp[np.where(np.abs(xp) == np.nanmin(np.abs(xp)))] = np.nan
    ycenter = yp[np.where(np.abs(xp) == np.nanmin(np.abs(xp)))][0]
  planet = pl.Circle((0, ycenter), trn.transit.RpRs, color='DarkBlue', alpha=1.)
  inset2.add_artist(planet)
  inset2.set_title('Top View', fontweight='bold', fontsize=9)
  inset2.set_aspect('equal','datalim')
  
  # The orbit itself
  with np.errstate(invalid='ignore'):
    ax2.plot(x, y, '-', color='DarkBlue', lw = 1. if per < 30. else 
                                               max(1. - (per - 30.) / 100., 0.3) )

  # The planet
  with np.errstate(invalid = 'ignore'):
    ycenter = y[np.where(np.abs(x) == np.nanmin(np.abs(x)))][0]
  while ycenter > 0:
    x[np.where(np.abs(x) == np.nanmin(np.abs(x)))] = np.nan
    ycenter = y[np.where(np.abs(x) == np.nanmin(np.abs(x)))][0]
  planet = pl.Circle((0, ycenter), trn.transit.RpRs, color='DarkBlue', alpha=1.)
  ax2.add_artist(planet)
  
  # Force aspect
  if xlim is None:
    xlim = 1.1 * max(np.nanmax(x), np.nanmax(-x))
  ax2.set_ylim(-xlim/3.2,xlim/3.2)
  ax2.set_xlim(-xlim,xlim)
  
  ax2.set_xlabel(r'X (R$_\star$)', fontweight='bold')
  ax2.set_ylabel(r'Y (R$_\star$)', fontweight='bold')
  ax1.set_title(plottitle, fontsize=12)
  
  if not compact:
    rect = 0.925,0.55,0.2,0.35
    ax3 = fig.add_axes(rect)
    ax3.xaxis.set_visible(False)
    ax3.yaxis.set_visible(False)

    # Table of parameters
    ltable = [ r'$P:$',
               r'$e:$',
               r'$i:$',
               r'$\omega:$',
               r'$\rho_\star:$',
               r'$M_p:$',
               r'$R_p:$',
               r'$q_1:$',
               r'$q_2:$']
    rtable = [ r'$%.4f\ \mathrm{days}$' % trn.transit.per,
               r'$%.5f$' % trn.transit.ecc,
               r'$%.4f^\circ$' % inc,
               r'$%.3f^\circ$' % (trn.transit.w*180./np.pi),
               r'$%.5f\ \mathrm{g/cm^3}$' % trn.transit.rhos,
               r'$%.5f\ M_\star$' % trn.transit.MpMs,
               r'$%.5f\ R_\star$' % trn.transit.RpRs,
               r'$%.5f$' % trn.limbdark.q1,
               r'$%.5f$' % trn.limbdark.q2]
    yt = 0.875
    for l,r in zip(ltable, rtable):
      ax3.annotate(l, xy=(0.25, yt), xycoords="axes fraction", ha='right', fontsize=16)
      ax3.annotate(r, xy=(0.35, yt), xycoords="axes fraction", fontsize=16)
      yt -= 0.1

  fig.savefig(plotname, bbox_inches='tight')
  pl.close()

def PlotImage(M=0., obl=0., bkgcolor = 'white', bkgimage = None,
              long0 = 0., image_map = 'earth', trail = False, ax = None,
              trailpts = 5000, xlims = None, ylims = None, fullplot = False, 
              lightcurve = False, starcolor = (1.0, 0.85, 0.1), **kwargs):
  '''
  
  '''

  kwargs.update({'fullorbit': True})
  if trail:
    kwargs.update({'exppts': 10, 'exp_time': 10 * kwargs['per'] / trailpts})
  trn = Transit(**kwargs)
  trn.Compute()
  
  # Sky-projected motion
  time = trn.arrays.time
  ti = np.argmax(-np.abs(( (trn.arrays.M + 2*np.pi) % (2*np.pi)) - M))                # Find index closest to desired mean anomaly

  x = trn.arrays.x
  y = trn.arrays.y
  z = trn.arrays.z
  
  # Params
  RpRs = trn.transit.RpRs
  u1 = trn.limbdark.u1
  u2 = trn.limbdark.u2
  
  # OBSOLETE: Mask the star
  #for j in range(trn.arrays.nend - trn.arrays.nstart):
  #  if (x[j]**2 + y[j]**2) < 1. and (z[j] > 0):
  #    x[j] = np.nan
  #    y[j] = np.nan

  if ax is None:
    fig = pl.figure()                                                                 # fig = pl.figure(figsize=(298./100, 218./100), dpi=100)
    if not lightcurve:
      ax = pl.subplot(111)
    else:
      ax = pl.subplot2grid((4, 1), (0, 0), rowspan=3)
      lc = pl.subplot2grid((4, 1), (3, 0), sharex=ax)
      fig.subplots_adjust(hspace = 0.05)
  else:
    fig = None
  
  if fullplot:
    xmin = min(-2.5, np.nanmin(x) - 5*RpRs)
    xmax = max(2.5, np.nanmax(x) + 5*RpRs)
    ymin = min(-2., np.nanmin(y) - 5*RpRs)
    ymax = max(2., np.nanmax(y) + 5*RpRs)
  else:  
    if xlims is None:
      xmin = min(-2.5, x[ti] - 5*RpRs)
      xmax = max(2.5, x[ti] + 5*RpRs)
    else:
      xmin, xmax = xlims
    if ylims is None:
      ymin = min(-2., y[ti] - 5*RpRs)
      ymax = max(2., y[ti] + 5*RpRs)
    else:
      ymin, ymax = ylims
  
  ax.set_xlim(xmin, xmax)
  ax.set_ylim(ymin, ymax)
  ax.xaxis.set_visible(False)
  ax.yaxis.set_visible(False)
  ax.set_aspect('equal')
  
  if bkgimage is not None:
    im = Image.open(PSZGPATH + '/pysyzygy/maps/' + bkgimage + '.jpg')
    ax.imshow(im, extent=(xmin,xmax,ymin,ymax), zorder=-99)
  else:
    ax.patch.set_facecolor(bkgcolor)
  
  if z[ti] < 0: 
    zorder = -2
  else: 
    zorder = 2
  Star(ax, trn.limbdark, zorder = zorder, color = starcolor)
  Planet(ax, x = x[ti], y = y[ti], z = z[ti], r = RpRs, long0 = long0, 
         image_map=image_map)
  
  if trail:
    Trail(ax, x, y, z, ti, RpRs = RpRs)
  
  ax.axis('off')
  
  if lightcurve:
    f = trn.arrays.flux
    t = trn.arrays.time
    t = t - t[np.argmin(f)] + kwargs['per']/2.
    t = t % kwargs['per']                                                             # Fold it
    
    t = (t - t[np.argmin(t)])/(t[np.argmax(t)] - t[np.argmin(t)])                     # Normalize to [0,1]
    xmin, xmax = ax.get_xlim()                                                        # Normalize to top plot axes
    t *= (xmax - xmin)
    t += xmin
    
    t[np.argmax(t)] = np.nan
    lc.plot(t, f, '-', color="#4682b4", lw = 5, alpha = 0.75)
    
    for i in range(ti):
      if i == ti - 1:
        alpha = 1.
        mfc = "#4682b4"
        mec = 'r'
        zorder = 100
      else:
        alpha = 0.1*max(0., (i - (ti - 500.))/500.)**2
        mfc = 'r'
        mec = 'none'
        zorder = None
      lc.scatter(t[i], f[i], marker = 'o', s = 200, facecolor = mfc, edgecolor = mec, alpha = alpha, lw = 3, zorder = zorder)
    
    lc.xaxis.set_visible(False)
    lc.yaxis.set_visible(False)
    
    ymax = f[np.argmax(f)]
    ymin = f[np.argmin(f)]
    yrng = ymax - ymin
    ymax += 0.1*yrng
    ymin -= 0.1*yrng
    lc.set_ylim(ymin, ymax)
    
    lc.patch.set_facecolor('black')
    
  return fig, ax

def AnimateImage(obl=0., bkgcolor = 'white', bkgimage = None,
                 image_map = 'earth', trail = True,
                 nsteps = 1000, dpy = 4, delay = 3, plotname = 'transit', 
                 xlims = None, ylims = None, resize = None, 
                 size_inches = None, starcolor = (1.0, 0.85, 0.1), delete = True,
                 **kwargs):
  '''
  Note that dpy (= days_per_year) can be set negative for retrograde rotation
  
  '''
  subprocess.call(['mkdir', '-p', 'tmp'])
  frames = range(nsteps)
  M = np.linspace(0,2*np.pi,nsteps,endpoint=False)
  rotation = (np.linspace(0, -dpy, nsteps) % 1)*360 - 180
  
  if xlims is not None and ylims is not None: fullplot = False
  else: fullplot = True
  
  i = 1
  for f, long0 in zip(frames, rotation):
    sys.stdout.write("\rPlotting image %d/%d..." % (i, nsteps))
    sys.stdout.flush()
    fig, ax = PlotImage(M = M[f], obl=obl, bkgcolor = bkgcolor, bkgimage = bkgimage,
                        long0 = long0, image_map = image_map, trail = trail,
                        trailpts = max(1000, nsteps), fullplot = fullplot,
                        starcolor = starcolor,
                        xlims = xlims, ylims = ylims, **kwargs)
    if size_inches is not None:
      fig.set_size_inches(*size_inches)
      
    fig.savefig('tmp/%03d.png' % f, bbox_inches = 'tight')
    pl.close()
    i += 1
  print("")
  
  # Make gif
  if resize is not None:
    subprocess.call(['convert', '-delay', '%d' % delay, '-loop', '-1', 'tmp/*.png', 
                     '-resize', resize, '%s.gif' % plotname])
  else:
    subprocess.call(['convert', '-delay', '%d' % delay, '-loop', '-1', 'tmp/*.png', 
                     '%s.gif' % plotname])
  # Delete pngs
  if delete:
    subprocess.call(['rm', '-r', 'tmp'])