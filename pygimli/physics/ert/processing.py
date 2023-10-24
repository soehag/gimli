"""Utility functions for ERT data processing."""
import numpy as np
# from numpy import ma

import pygimli as pg
from .ert import createGeometricFactors


def uniqueERTIndex(data, nI=0, reverse=False):
    """Generate unique index from sensor indices A/B/M/N for matching

    Parameters
    ----------
    data : DataContainerERT
        data container holding a b m n field registered as indices (int)
    I : int [0]
        index to generate (multiply), by default (0) sensorCount
        if two data files with different sensorCount are compared make sure
        to use the same I for both
    reverse : bool [False]
        exchange current (A, B) with potential (M, N) for reciprocal analysis
    """
    if nI == 0:
        nI = data.sensorCount() + 1
    normABMN = {'a': np.minimum(data('a'), data('b')) + 1,
                'b': np.maximum(data('a'), data('b')) + 1,
                'm': np.minimum(data('m'), data('n')) + 1,
                'n': np.maximum(data('m'), data('n')) + 1}
    abmn = ['a', 'b', 'm', 'n']   # 1 2 8 7
    if reverse:
        abmn = ['m', 'n', 'a', 'b']   # 7 8 2 1
#        abmn = ['n', 'm', 'b', 'a']   # 7 8 2 1
    ind = 0
    for el in abmn:
        ind = ind * nI + normABMN[el]  # data(el)

    return np.array(ind, dtype=np.int64)

def generateDataFromUniqueIndex(ind, data=None, nI=None):
    """Generate data container from unique index."""
    scheme = pg.DataContainerERT()
    if isinstance(data, pg.DataContainer):
        scheme = pg.DataContainerERT(data)
    elif isinstance(data, pg.PosVector):
        scheme.setSensorPositions(data)
    elif isinstance(data, int):  # check for positions
        for i in range(data):
            scheme.createSensor([i, 0, 0])

    nI = nI or scheme.sensorCount() + 1
    scheme.resize(0)  # make sure all data are deleted
    scheme.resize(len(ind))
    nmba = np.zeros([len(ind), 4], dtype=int)
    for i in range(4):
        col = ind % nI
        ind -= col
        ind = ind // nI
        nmba[:, i] = col

    for i, tok in enumerate("nmba"):
        scheme[tok] = nmba[:, i] - 1

    scheme["valid"] = 1
    return scheme

def getReciprocals(data, change=False, remove=False):
    """Compute data reciprocity from forward and backward data.

    The reciprocity (difference between forward and backward array divided by
    their mean) is computed and saved under the dataContainer field 'rec'

    Parameters
    ==========
    data : pg.DataContainerERT
        input data container to be changed inplace
    change : bool [True]
        compute current-weighted mean of forward and backward values
    remove : bool [False]
        remove backward data that are present as forward data
    """
    if not data.allNonZero('r'):
        data.set('r', data('u') / data('i'))

    unF = uniqueERTIndex(data)
    unB = uniqueERTIndex(data, reverse=True)
    rF, rB = [], []
    rec = np.zeros(data.size())
    data.set('rec', pg.Vector(data.size()))
    for iB in range(data.size()):
        if unB[iB] in unF:
            iF = int(np.nonzero(unF == unB[iB])[0][0])
            rF.append(data('r')[iF])
            rB.append(data('r')[iB])
            rec[iB] = (rF[-1]-rB[-1]) / (rF[-1]+rB[-1]) * 2
            data('rec')[iF] = rec[iB]
            IF, IB = data('i')[iF], data('i')[iB]  # use currents for weighting
            if change and data('valid')[iF]:
                data('r')[iF] = (rF[-1] * IF + rB[-1] * IB) / (IF + IB)
                data('i')[iF] = (IF**2 + IB**2) / (IF + IB)  # according weight
                data('u')[iF] = data('r')[iF] * data('i')[iF]
                if remove:
                    data('valid')[iB] = 0  # for adding all others later on

    print(len(rF), "reciprocals")
    if remove:
        data.removeInvalid()


def extractReciprocals(fwd, bwd):
    """Extract reciprocal data from forward/backward DataContainers."""
    nMax = max(fwd.sensorCount(), bwd.sensorCount())
    unF = uniqueERTIndex(fwd, nI=nMax)
    unB = uniqueERTIndex(bwd, nI=nMax, reverse=True)
    rF, rB = [], []
    rec = np.zeros(bwd.size())
    both = pg.DataContainerERT(fwd)
    both.set('rec', pg.Vector(both.size()))
    back = pg.DataContainerERT(bwd)
    back.set('rec', pg.Vector(back.size()))
    for iB in range(bwd.size()):
        if unB[iB] in unF:
            iF = int(np.nonzero(unF == unB[iB])[0][0])
            rF.append(fwd('r')[iF])
            rB.append(bwd('r')[iB])
            rec[iB] = (rF[-1]-rB[-1]) / (rF[-1]+rB[-1]) * 2
            both('rec')[iF] = rec[iB]
            IF, IB = fwd('i')[iF], bwd('i')[iB]  # use currents for weighting
            both('r')[iF] = (rF[-1] * IF + rB[-1] * IB) / (IF + IB)
            both('i')[iF] = (IF**2 + IB**2) / (IF + IB)  # according to weight
            both('u')[iF] = fwd('r')[iF] * fwd('i')[iF]
            back('valid')[iB] = 0  # for adding all others later on
    print(len(rF), "reciprocals")
    back.removeInvalid()
    both.add(back)
    return rec, both

def combineMultipleData(DATA):
    """Combine multiple data containers into data/err matrices."""
    assert hasattr(DATA, '__iter__'), "DATA should be DataContainers or str!"
    if isinstance(DATA[0], str):  # read in if strings given
        DATA = [pg.DataContainerERT(data) for data in DATA]

    nEls = [data.sensorCount() for data in DATA]
    assert max(np.abs(np.diff(nEls))) == 0, "Electrodes not equal"
    uIs = [uniqueERTIndex(data) for data in DATA]
    uI = np.unique(np.hstack(uIs))
    scheme = generateDataFromUniqueIndex(uI, DATA[0])
    uI = uniqueERTIndex(scheme)  # why is this not the same?
    R = np.ones([scheme.size(), len(DATA)]) * np.nan
    ERR = np.zeros_like(R)
    scheme.save("bla.shm", "a b m n")
    if not scheme.haveData('k'):  # just do that only once
        scheme['k'] = createGeometricFactors(scheme)  # check numerical

    for i, di in enumerate(DATA):
        ii = np.searchsorted(uI, uIs[i])
        if not di.haveData('r'):
            if di.allNonZero('u') and di.allNonZero('i'):
                di['r'] = di['u']/di['i']
            elif di.allNonZero('rhoa'):
                di['r'] = di['rhoa'] / scheme['k'][ii]

        R[ii, i] = di['r']
        ERR[ii, i] = di['err']

    RHOA = np.reshape(scheme['k'], [-1, 1]) * R
    return scheme, RHOA, ERR
