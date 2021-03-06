"""Dataset handler."""
from __future__ import print_function

import sys

import numpy as np

import pandas as pd

from theano import config

__author__ = "Gianluca Corrado"
__copyright__ = "Copyright 2016, Gianluca Corrado"
__license__ = "MIT"
__maintainer__ = "Gianluca Corrado"
__email__ = "gianluca.corrado@unitn.it"
__status__ = "Production"


class Dataset(object):
    """General dataset."""

    def __init__(self, fp, fr, standardize_proteins=False,
                 standardize_rnas=False, verbose=True):
        """
        Constructor.

        Parameters
        ----------
        fp : str
            The name of the HDF5 file containing features for the proteins.

        fr : str
            The name of the HDF5 file containing features for the RNAs.

        standardize_proteins : bool (default : False)
            Whether protein features should be standardized.

        standardize_rnas : bool (default : False)
            Whether RNAs features should be standardized.

        verbose : bool (default : True)
            Print information at STDOUT.
        """
        self.verbose = verbose

        def standardize(x):
            x_mean = x.mean(axis=1)
            x_std = x.std(axis=1)
            x_std[x_std == 0.0] = 1.0
            return ((x.T - x_mean) / x_std).T

        store = pd.io.pytables.HDFStore(fp)
        self.Fp = store.features.astype(config.floatX)
        store.close()
        if self.verbose:
            print('Protein features of shape', self.Fp.shape)
            sys.stdout.flush()

        if standardize_proteins:
            if self.verbose:
                print('Standardizing protein features...', end=' ')
                sys.stdout.flush()
            self.Fp = standardize(self.Fp)
            if self.verbose:
                print('Done.')
                sys.stdout.flush()

        store = pd.io.pytables.HDFStore(fr)
        self.Fr = store.features.astype(config.floatX)
        store.close()
        if self.verbose:
            print('RNA features of shape', self.Fr.shape)
            sys.stdout.flush()

        if standardize_rnas:
            if self.verbose:
                print('Standardizing RNA features...', end=' ')
                sys.stdout.flush()
            self.Fr = standardize(self.Fr)
            if self.verbose:
                print('.Done.')
                sys.stdout.flush()

    def load(self):
        """Load dataset in memory."""
        raise NotImplementedError()


class TrainDataset(Dataset):
    """Training dataset."""

    def __init__(self, fp, fr, y, standardize_proteins=False,
                 standardize_rnas=False, verbose=True, seed=1234):
        """
        Constructor.

        Parameters
        ----------
        fp : str
            The name of the HDF5 file containing features for the proteins.

        fr : str
            The name of the HDF5 file containing features for the RNAs.

        y : str
            The name of the HDF5 file containing the interaction matrix.
            The dataframe inside this file has proteins as columns and RNAs as
            rows (index). A NaN is expected there if the interaction is
            supposedly unknown.

        standardize_proteins : bool (default : False)
            Whether protein features should be standardized.

        standardize_rnas : bool (default : False)
            Whether RNAs features should be standardized.

        verbose : bool (default : True)
            Print information at STDOUT.

        seed : int (default : 1234)
            Seed for random number generator.
        """
        super(TrainDataset, self).__init__(fp, fr, standardize_proteins,
                                           standardize_rnas, verbose)

        store = pd.io.pytables.HDFStore(y)
        self.Y = store.matrix.astype(config.floatX)
        store.close()
        if self.verbose:
            print('Interaction matrix of shape', self.Y.shape)
            sys.stdout.flush()

        assert self.Fp.shape[1] == self.Y.shape[1] and \
            self.Fr.shape[1] == self.Y.shape[0]

        self.seed = seed

    def load(self):
        """
        Load dataset in memory.

        Return
        ------
        dataset : list
            List of triplets (p,r,i) representing the batches.
            Each batch is made of all the labeled examples of one RNA.
        """
        if self.verbose:
            print('\nmaking training set (%d user%s and %d item%s)...' % (
                len(self.Y.columns), (len(self.Y.columns) > 1) * 's',
                len(self.Y.index), (len(self.Y.index) > 1) * 's'))
            sys.stdout.flush()

        protein_input_dim = self.Fp.shape[0]
        rna_input_dim = self.Fr.shape[0]
        dataset = []

        num_pos = 0
        num_neg = 0
        num_batches = 0

        progress = 0
        for (n, rna) in enumerate(self.Y.index):
            if n % (len(self.Y.index) / 10) == 0:
                if self.verbose:
                    print(str(progress) + "%", end=' ')
                    sys.stdout.flush()
                progress += 10
            num_examples = self.Y.loc[rna].count().sum()  # understands NaN
            p = np.zeros((num_examples, protein_input_dim)
                         ).astype(config.floatX)
            r = np.zeros((num_examples, rna_input_dim)).astype(config.floatX)
            i = np.zeros((num_examples, 1)).astype(config.floatX)

            index = 0
            for protein in self.Y.columns:
                if np.isnan(self.Y[protein][rna]):
                    continue
                p[index] = self.Fp[protein]
                r[index] = self.Fr[rna]
                i[index] = self.Y[protein][rna]
                if i[index] > 0:
                    num_pos += 1
                else:
                    num_neg += 1
                index += 1

            perm = np.random.permutation(range(num_examples))
            p = np.matrix(p[perm])
            r = np.matrix(r[perm])
            i = np.array(i[perm].flatten())

            dataset.append((p, r, i))
            num_batches += 1

        np.random.seed(self.seed)
        np.random.shuffle(dataset)

        if self.verbose:
            print("")
            print("Training set created")
            print("\twith %i examples" % (num_pos + num_neg))
            print("\tnumber of positives: %i" % num_pos)
            print("\tnumber of negatives: %i" % num_neg)
            print("\tnumber of batches: %i" % num_batches)
            sys.stdout.flush()

        return dataset


class PredictDataset(Dataset):
    """Test dataset."""

    def __init__(self, fp, fr, to_predict=None, standardize_proteins=False,
                 standardize_rnas=False, verbose=True):
        """
        Constructor.

        Parameters
        ----------
        fp : str
            The name of the HDF5 file containing features for the proteins.

        fr : str
            The name of the HDF5 file containing features for the RNAs.

        to_predict : list (default : None)
            List of proteins from Fp to predict.
            If None all the proteins will be predicted.

        standardize_proteins : bool (default : False)
            Whether protein features should be standardized.

        standardize_rnas : bool (default : False)
            Whether RNAs features should be standardized.

        verbose : bool (default : True)
            Print information at STDOUT.
        """
        super(PredictDataset, self).__init__(
            fp, fr, standardize_proteins, standardize_rnas, verbose)
        self.to_predict = to_predict
        if self.to_predict is not None:
            self.Fp = self.Fp[self.to_predict]

    def load(self):
        """
        Load dataset in memory.

        Return
        ------
        Examples to predict. For each example:
            - p contains the protein features,
            - r contains the RNA features,
            - p_names contains the name of the protein,
            - r_names contains the name of the RNA.

        """
        if self.verbose:
            print('\nPreparing dataset (%d protein%s and %d RNA%s)...' % (
                self.Fp.shape[1], (self.Fp.shape[1] > 1) *
                's', self.Fr.shape[1],
                (self.Fr.shape[1] > 1) * 's'), end=' ')
            sys.stdout.flush()

        protein_input_dim = self.Fp.shape[0]
        rna_input_dim = self.Fr.shape[0]
        num_examples = self.Fp.shape[1] * self.Fr.shape[1]
        p = np.zeros((num_examples, protein_input_dim)).astype(config.floatX)
        p_names = []
        r = np.zeros((num_examples, rna_input_dim)).astype(config.floatX)
        r_names = []
        index = 0
        for protein in self.Fp.columns:
            for rna in self.Fr.columns:
                p[index] = self.Fp[protein]
                p_names.append(protein)
                r[index] = self.Fr[rna]
                r_names.append(rna)
                index += 1

        if self.verbose:
            print("Done.\n")

        return (p, np.array(p_names), r, np.array(r_names))
