from __future__ import print_function
import numpy as np
from theano import function, shared, config
import theano.tensor as T
# from lasagne.updates import sgd

__author__ = "Gianluca Corrado"
__copyright__ = "Copyright 2016, Gianluca Corrado"
__license__ = "MIT"
__maintainer__ = "Gianluca Corrado"
__email__ = "gianluca.corrado@unitn.it"
__status__ = "Production"

class Model():
    """Factorization model"""
    def __init__(self,n,m,sp,sr,irange=0.01,learning_rate=0.01,lambda_reg=0.01,verbose=True,seed=1234):
        """
        Params
        ------
        n : int
            Number of protein features.

        m : int
            Number of RNA features.

        sp : int
            Size of the protein latent space.

        sr : int
            Size of the RNA latent space.

        irange : float (default : 0.01)
            Initialization range for the model weights.

        learning_rate : float (default : 0.01)
            Learning rate for the weights update.

        lambda_reg : (default : 0.01)
            Lambda parameter for the regularization.

        verbose : bool (default : True)
            Print information at STDOUT.

        seed : int (default : 1234)
            Seed for random number generator.
        """

        if verbose:
            print("Compiling model...", end=' ')

        np.random.seed(seed)
        # explictit features for proteins
        Fp = T.matrix("Fp",dtype=config.floatX)
        # explictit features for RNAs
        Fr = T.matrix("Fr",dtype=config.floatX)
        # Correct label
        y = T.vector("y")

        # projection matrix for proteins
        self.Ap = shared(((.5 - np.random.rand(sp,n)) * irange).astype(config.floatX), name="Ap")
        self.bp = shared(((.5 - np.random.rand(sp)) * irange).astype(config.floatX), name="bp")
        # projection matrix for RNAs
        self.Ar = shared(((.5 - np.random.rand(sr,m)) * irange).astype(config.floatX), name="Ar")
        self.br = shared(((.5 - np.random.rand(sr)) * irange).astype(config.floatX), name="br")
        # generalization matrix
        self.B = shared(((.5 - np.random.rand(sp,sr)) * irange).astype(config.floatX), name="B")

        # Latent space for proteins
        P = T.nnet.sigmoid(T.dot(Fp,self.Ap.T) + self.bp)
        # Latent space for RNAs
        R = T.nnet.sigmoid(T.dot(Fr,self.Ar.T) + self.br)
        # Predicted output
        y_hat = T.nnet.sigmoid(T.sum(T.dot(P,self.B) * R, axis=1))

        def _regularization():
            """Frobenius norm of the parameters, normalized by the size of the matrices"""
            norm_proteins = self.Ap.norm(2) + self.bp.norm(2)
            norm_rnas = self.Ar.norm(2) + self.br.norm(2)
            norm_B = self.B.norm(2)

            num_proteins = self.Ap.flatten().shape[0] + self.bp.shape[0]
            num_rnas = self.Ar.flatten().shape[0] + self.br.shape[0]
            num_B = self.B.flatten().shape[0]

            return (norm_proteins/num_proteins + norm_rnas/num_rnas + norm_B/num_B)/3

        # mean squadred error
        cost_ = (T.sqr(y - y_hat)).mean()
        reg = lambda_reg*_regularization()
        cost = cost_+reg

        # compute sgd updates
        g_Ap,g_bp,g_Ar,g_br,g_B = T.grad(cost,[self.Ap,self.bp,self.Ar,self.br,self.B])
        updates = ((self.Ap, self.Ap - learning_rate*g_Ap),
                    (self.bp, self.bp - learning_rate*g_bp),
                    (self.Ar, self.Ar - learning_rate*g_Ar),
                    (self.br, self.br - learning_rate*g_br),
                    (self.B, self.B - learning_rate*g_B))
        # updates = sgd(cost, [self.ap,self.bp,self.ar,self.br,self.B],learning_rate=learning_rate)

        # training step
        self.train = function(
                inputs=[Fp,Fr,y],
                outputs=[y_hat,cost],
                updates=updates)
        # test
        self.test = function(
                inputs=[Fp,Fr,y],
                outputs=[y_hat,cost])

        # predict
        self.predict = function(
                inputs=[Fp,Fr],
                outputs=[y_hat])

        if verbose:
            print("Done.")

    def get_params(self):
        """Return the parameters of the model"""
        return {'Ap':self.Ap.get_value(),'bp':self.bp.get_value(), 'Ar':self.Ar.get_value(),'br':self.br.get_value(),'B':self.B.get_value()}