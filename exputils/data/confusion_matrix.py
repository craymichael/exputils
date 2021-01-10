"""Given this has been a reoccuring trend where the confusion matrix needs
calculated and certain metrics need calculated FROM the confusion matrix, add
__tested__ metrics derived from the confusion matrix for efficient
computation.
"""
import logging
import os

import h5py
import numpy as np
import pandas as pd
from plotly import graph_objects as go
from scipy.stats import gmean
from sklearn.metrics import confusion_matrix

from exputils.io import create_filepath


class ConfusionMatrix(object):
    """Confusion matrix for nominal data that wraps the
    sklearn.metrics.confusion_matrix. Rows are the known labels and columns are
    the predictions.
    """
    def __init__(self, targets, preds=None, labels=None, *args, **kwargs):
        """
        Parameters
        ----------
        targets : np.ndarray()
            The confusion matrix to wrap, or the target labels.
        preds : np.ndarray, optional
        labels : list, optional
            The labels for the row and columns of the confusion matrix
        """
        if preds is None:
            if (
                (
                    isinstance(targets, np.ndarray)
                    or isinstance(targets, pd.DataFrame)
                )
                and len(targets.shape) == 2
                and targets.shape[0] == targets.shape[1]
            ):
                # If given an existing matrix as a confusion matrix
                self.labels = labels
                self.mat = np.array(targets)
            else:
                raise TypeError(' '.join([
                    'targets type is expected to be of type `np.ndarray`, but',
                    f'recieved type of {type(targets)}.',
                ]))
        elif preds is not None:
            # Calculate the confusion matrix from targets and preds with sklearn
            self.mat = confusion_matrix(
                targets,
                preds,
                labels=labels,
                *args,
                **kwargs,
            )

            self.labels = labels

    # TODO methods for the metrics able to be derived from the confusion matrix
    # f score (1 and beta)
    # informedness # This may not generalize to multi class
    # mathew's correlation coefficient (MCC)
    # ROC
    # ROC AUC
    # TOC
    # TOC AUC

    def accuracy(self, label_weights=None):
        #return (self.true_pos + self.true_negatives) / all = Trues / all
        if label_weights is not None:
            raise NotImplementedError('Use sklearn.metrics on the samples')
        return np.diagonal(self.mat).sum() / self.mat.sum()

    def error_rate(self, label_weights=None):
        if label_weights is not None:
            raise NotImplementedError('Use sklearn.metrics on the samples')
        return 1.0 - self.accuracy()

    def true_rate(self, average=False, label_weights=None):
        """Recall, sensitivity, hit rate, or true positive rate. This is
        calculated the same as specificity, selectivity or true negative rate,
        but on the different classes.

        Parameters
        ----------
        average : bool
            if True, averages all true class rates together. Otherwise, returns
            the true rate per class in order of labels.
        """
        recalls = np.diagonal(self.mat) / self.mat.sum(axis=1)

        if average:
            if label_weights is not None:
                raise NotImplementedError('Use sklearn.metrics on the samples')
            # Provide the averaged true class rates (balanced accuracy)
            return recalls.mean()

        # Provide the recall per class
        return recalls

    def f_score(self, beta=1, average='macro', label_weights=None):
        # average match sklearn f1_score: None, "binary", micro, macro,
        # weighted
        raise NotImplementedError('Use sklearn.metrics on the samples')

    def mcc(self, label_weights=None):
        """Mathew's Correlation Coefficient, R_k, a generalizatin of Pearson's
        correlation coefficient.
        """
        actual = self.mat.sum(1)
        predicted = self.mat.sum(0)
        correctly_pred = np.diagonal(self.mat).sum()
        total_sqrd = self.mat.sum()**2

        return (
            correctly_pred * self.mat.sum() - np.dot(actual, predicted) /
            (
                np.sqrt(total_sqrd - np.dot(predicted, predicted))
                * np.sqrt(total_sqrd - np.dot(actual, actual))
            )
        )

    def mutual_information(self, normalized=None, weights=None):
        """The confusion matrix is the joint probability mass function when
        the values are divided by the total of the confusion matrix.
        """
        # TODO weighted variants, more normalized variants, adjusted, etc.
        # TODO replicate the normalization method in scikitlearn but from a
        # given confusion matrix.
        #   NMI using "arithemtic" in scikit learn is: MI / mean(H(X),H(Y))
        #   thus, it follow geometric mean is similarly used, as is min() and
        #   max()

        joint_distrib = self.mat / self.mat.sum()
        marginal_actual = joint_distrib.sum(1).reshape(-1,1)
        marginal_pred = joint_distrib.sum(0).reshape(-1,1)

        # TODO need a unit test for this
        joint_flat = joint_distrib.flatten()
        denom_flat = np.repeat(marginal_actual, self.mat.shape[1], 1) \
            * np.repeat(marginal_pred, self.mat.shape[1], 1).T

        if (
            isinstance(weights, np.ndarray)
            and weights.shape == joint_distrib.shape
        ):
            # Weighted MI from Guiasu 1977
            mutual_info = (
                weights.flatten() * joint_flat
                * np.log2(joint_flat / denom_flat)
            ).sum()
        else:
            mutual_info = (joint_flat * np.log2(joint_flat / denom_flat)).sum()

        if normalized is None:
            return mutual_info
        if normalized == 'arithmetic':
            return mutual_info / np.mean((self.entropy(0), self.entropy(1)))
        if normalized == 'geometric':
            return mutual_info / gmean((self.entropy(0), self.entropy(1)))
        if normalized == 'min':
            return mutual_info / np.minimum(self.entropy(0), self.entropy(1))
        if normalized == 'max':
            return mutual_info / np.maximum(self.entropy(0), self.entropy(1))
        if normalized == 'additive':
            # Redundancy
            return mutual_info / (self.entropy(0) + self.entropy(1))
        if normalized == 'harmonic':
            # Symmetric uncertainty: harmonic mean of the 2 uncertainty coef.s
            return mutual_info / (2 * (self.entropy(0) + self.entropy(1)))
        if normalized == 'iqr':
            # Information Quality Ratio (IQR) or special case of dual total
            # correlation
            return mutual_info / (
                self.entropy(0) + self.entropy(1) - mutual_info
            )

        raise ValueError('Unexpected value for `normalized`: {normalized}')

    def entropy(self, axis):
        """Returns the entropy of either the predictions or actual values."""
        # TODO need a unit test for this
        if axis == 0 or axis == 'pred' or axis == 'predicted':
            marginal = self.mat.sum(0)
        elif axis == 1 or axis == 'actual':
            marginal = self.mat.sum(1)
        else:
            raise ValueError(f'Unexpected value for `axis`: {axis}')
        return -(marginal * np.log2(marginal)).sum()

    # TODO Reduction of classes including two class subsets to obtain
    # Binarization
    #   e.g. given set of labels as known and set of labels as unknown return
    #   binary confusion matrix of knowns vs uknowns

    # TODO combination of different confusion matrices objects into one.

    # TODO Visualizations
    # ROC
    # TOC

    def heatmap(
        self,
        filepath=None,
        overwrite=False,
        **kwargs,
    ):
        """Confusion matrix visualized as a heat map using plotly."""
        if self.labels is None:
            labels = np.arange(len(self.mat))
        else:
            labels = self.labels

        # Provide more informative (overridable) default layout for the heatmap
        layout_kwargs = dict(
            title = '<b>Confusion Matrix</b>',
            xaxis = {'side': 'top'},
            yaxis = {'autorange': 'reversed'},
        )
        # If layout override exists, then update defaults
        if 'layout' in kwargs:
            if isinstance(kwargs['layout'], dict):
                layout_kwargs.update(kwargs['layout'])
                kwargs['layout'] = go.Layout(**layout_kwargs)
            else:
                layout_kwargs.update(kwargs['layout'])
                kwargs['layout'] = go.Layout(**layout_kwargs).update(
                    **kwargs['layout'],
                )
        else:
            kwargs['layout'] = go.Layout(**layout_kwargs)


        fig = go.Figure(
            data=go.Heatmap(
                z=self.mat,
                x=labels,
                y=labels,
                **kwargs.pop('data', {}),
            ),
            **kwargs,
        )

        if filepath is None:
            return fig

        # Otherwise save plot to filepath
        fig.write_image(create_filepath(filepath, overwrite=overwrite))

    def save(
        self,
        filepath,
        filetype='csv',
        conf_mat_key='confusion_matrix',
        overwrite=False,
        *args,
        **kwargs,
    ):
        """Saves the current confusion matrix to the given filepath."""
        if not isinstance(filetype, str):
            raise TypeError(' '.join([
                'Expected filetype to be a str: "csv", "tsv", "hdf5", or',
                f'"h5"; not type `{type(filetype)}`',
            ]))

        filetype = filetype.lower()
        filepath = create_filepath(filepath, overwrite=overwrite)

        if filetype == 'csv' or filetype == 'tsv':
            pd.DataFrame(self.mat, columns=self.labels).to_csv(
                filepath,
                index=False,
                *args,
                **kwargs,
            )
        else: #HDF5
            with h5py.File(filepath, 'r') as h5f:
                h5f['labels'] = self.labels.astype(np.string_)
                h5f[conf_mat_key] = self.mat


def load_confusion_mat(
    filepath,
    sep=',',
    filetype=None,
    names=None,
    conf_mat_key='confusion_matrix',
    *args,
    **kwargs,
):
    """Convenience function that loads the confusion matrix from the given
    filepath in given common formats. Loading from CSV relies on
    pandas.read_csv(*args, **kwargs).
    """
    if filetype is None:
        # Infer filetype from filepath if filetype is not given
        parts = filepath.rpartition('.')

        if not parts[0]:
            raise ValueError(' '.join([
                'filetype is `None` and no file extention present in',
                'given filepath.',
            ]))

        if parts[2] and os.path.sep in parts[2]:
            raise ValueError(' '.join([
                'filetype is `None` and no file extention present in',
                'given filepath.',
            ]))

        filetype = parts[2].lower()
        if filetype == 'csv':
            sep = ','
            #filetype = 'csv'
        elif filetype == 'tsv':
            sep = '\t'
            #filetype = 'tsv'
        elif filetype == 'hdf5' or filetype == 'h5':
            filetype = 'hdf5'
        else:
            raise ValueError(' '.join([
                'filetype is `None` and file extention present in',
                'given filepath is not "csv", "tsv", "hdf5", or "h5".',
            ]))
    elif isinstance(filetype, str):
        # lowercase filetype and check if an expected extension
        filetype = filetype.lower()
        if filetype not in {'csv', 'tsv', 'hdf5', 'h5'}:
            raise TypeError(' '.join([
                'Expected filetype to be a str: "csv", "tsv", "hdf5", or',
                f'"h5", not `{filetype}`',
            ]))
    else:
        raise TypeError(' '.join([
            'Expected filetype to be a str: "csv", "tsv", "hdf5", or',
            f'"h5", not of type `{type(filetype)}`',
        ]))

    if filepath == 'csv' or 'tsv':
        loaded_confusion_mat = pd.read_csv(
            filepath,
            sep=sep,
            names=names,
            *args,
            **kwargs,
        )

        assert (
            len(loaded_confusion_mat.shape) == 2
            and loaded_confusion_mat.shape[0] == loaded_confusion_mat.shape[1]
        )

        if names is None:
            labels = np.array(loaded_confusion_mat.columns)
        else:
            labels = None
    else:  # HDF5
        with h5py.File(filepath, 'r') as h5f:
            if 'labels' in h5f.keys():
                if names is not None:
                    logging.warning(' '.join([
                        '`names` is provided while "labels" exists in the',
                        'hdf5 file! `names` is prioritized of the labels',
                        'in hdf5 file.',
                    ]))
                    labels = names
                else:
                    labels = h5f['labels'][:]

            loaded_confusion_mat = h5f[conf_mat_key][:]

    return ConfusionMatrix(loaded_confusion_mat, labels=labels)
