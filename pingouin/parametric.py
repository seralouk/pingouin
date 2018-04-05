# Author: Raphael Vallat <raphaelvallat9@gmail.com>
# Date: April 2018
import numpy as np

__all__ = ["gzscore", "test_normality", "test_homoscedasticity", "test_dist",
           "test_sphericity", "rm_anova"]


def gzscore(x):
    """Compute the geometric standard score of a 1D array.

    Geometric Z-score are better than arithmetic z-scores when the data
    comes from a log-normal or chi-squares distribution.

    Parameters
    ----------
    x: array_like
        Array of raw values

    Returns
    -------
    gzscore: array_like
        Array of geometric z-scores (gzscore.shape == x.shape)
    """
    from scipy.stats import gmean
    # Geometric mean
    geo_mean = gmean(x)
    # Geometric standard deviation
    gstd = np.exp(np.sqrt(np.sum((np.log(x / geo_mean))**2) / (len(x) - 1)))
    # Geometric z-score
    return np.log(x / geo_mean) / np.log(gstd)

# MAIN FUNCTIONS


def test_normality(*args, alpha=.05):
    """Test normality of an array.

    Parameters
    ----------
    sample1, sample2,... : array_like
        Array of sample data. May be different lengths.

    Returns
    -------
    normal: boolean
        True if x comes from a normal distribution.
    p: float
        P-value.
    """
    from scipy.stats import shapiro
    # Handle empty input
    for a in args:
        if np.asanyarray(a).size == 0:
            return np.nan, np.nan

    k = len(args)
    p = np.zeros(k)
    normal = np.zeros(k, 'bool')
    for j in range(k):
        _, p[j] = shapiro(args[j])
        normal[j] = True if p[j] > alpha else False

    if k == 1:
        normal = bool(normal)
        p = float(p)

    return normal, p


def test_homoscedasticity(*args, alpha=.05):
    """Test equality of variance.

    If data are normally distributed, uses Bartlett (1937).
    If data are not-normally distributed, uses Levene (1960).

    Parameters
    ----------
    sample1, sample2,... : array_like
        Array of sample data. May be different lengths.

    Returns
    -------
    equal_var: boolean
        True if data have equal variance.
    p: float
        P-value.
    """
    from scipy.stats import levene, bartlett
    # Handle empty input
    for a in args:
        if np.asanyarray(a).size == 0:
            return np.nan, np.nan

    k = len(args)
    if k < 2:
        raise ValueError("Must enter at least two input sample vectors.")

    # Test normality of data
    normal, _ = test_normality(*args)
    if np.count_nonzero(normal) != normal.size:
        # print('Data are not normally distributed. Using Levene test.')
        _, p = levene(*args)
    else:
        _, p = bartlett(*args)

    equal_var = True if p > alpha else False
    return equal_var, p


def test_dist(*args, dist='norm'):
    """Anderson-Darling test for data coming from a particular distribution.

    Parameters
    ----------
    sample1, sample2,... : array_like
        Array of sample data. May be different lengths.

    Returns
    -------
    from_dist: boolean
        True if data comes from this distribution.
    """
    from scipy.stats import anderson
    # Handle empty input
    for a in args:
        if np.asanyarray(a).size == 0:
            return np.nan, np.nan

    k = len(args)
    from_dist = np.zeros(k, 'bool')
    sig_level = np.zeros(k)
    for j in range(k):
        st, cr, sig = anderson(args[j], dist=dist)
        from_dist[j] = True if (st > cr).any() else False
        sig_level[j] = sig[np.argmin(np.abs(st - cr))]

    if k == 1:
        from_dist = bool(from_dist)
        sig_level = float(sig_level)
    return from_dist, sig_level


def test_sphericity(X, alpha=.05):
    """Mauchly's test for sphericity

    Warning: there are some differences with the output of ez.
    This function needs to be further tested against SPSS and R.

    Parameters
    ----------
    X : array_like
        Multivariate data matrix
    alpha: float, optional
        Significance level

    Returns
    -------
    sphericity: boolean
        True if data have the sphericity property.
    p: float
        P-value.
    """
    from scipy.stats import chi2
    n, k = X.shape
    d = k - 1
    # Covariance matrix
    C = np.cov(X, rowvar=0, ddof=k) * k
    # Mauchly's statistic
    W = np.linalg.det(C) / (np.trace(C) / d)**d
    # Chi-square statistic
    chi_sq = np.log(W) * ((2 * d**2 + d + 2) / 6 *
                          d - n - np.linalg.matrix_rank(X))
    # Degree of freedom
    ddof = d * (d + 1) / 2
    # P-value
    p = chi2.sf(chi_sq, ddof)
    sphericity = True if p > alpha else False
    return sphericity, W, p


def rm_anova(dv=None, within=None, data=None):
    """Compute one-way repeated measures ANOVA from a pandas DataFrame.

    Tested against mne.stats.f_mway_rm and ez R package.

    Parameters
    ----------
    dv : string
        Name of column containing the dependant variable.
    within: string
        Name of column containing the within factor.
    data: pandas DataFrame
        DataFrame

    Returns
    -------
    aov : DataFrame
        ANOVA summary
    """
    import pandas as pd
    from scipy.stats import f
    rm = list(data[within].unique())
    n_rm = len(rm)
    n_obs = int(data.groupby(within)[dv].count().max())

    # Calculating SStime
    grp_with = data.groupby(within)[dv]
    sstime = n_obs * np.sum((grp_with.mean() - grp_with.mean().mean())**2)

    # Calculating SSw
    ssw = np.zeros(n_rm)
    for i, (name, group) in enumerate(grp_with):
        ssw[i] = np.sum((group - group.mean())**2)
    sswithin = np.sum(ssw)

    # Calculating SSsubjects and SSerror
    data['Subj'] = np.tile(np.arange(n_obs), n_rm)
    grp_subj = data.groupby('Subj')[dv]
    sssubj = n_rm * np.sum((grp_subj.mean() - grp_subj.mean().mean())**2)
    sserror = sswithin - sssubj

    # Calculate MStime
    ddof1 = n_rm - 1
    ddof2 = ddof1 * (n_obs - 1)
    mserror = sserror / (ddof2 / ddof1)
    fval = sstime / mserror
    p_unc = f(ddof1, ddof2).sf(fval)

    # Compute sphericity using Mauchly's test
    # Sphericity = pairwise differences in variance between the samples are
    # ALL equal.
    data_pivot = data.pivot(index='Subj', columns=within, values=dv).dropna()
    # Test using a more stringent threshold of p<.01
    sphericity, W_mauchly, p_mauchly = test_sphericity(
        data_pivot.as_matrix(), alpha=.01)
    correction = True if not sphericity else False

    # If required, apply Greenhouse-Geisser correction for sphericity
    if correction:
        # Compute covariance matrix
        v = data_pivot.cov().as_matrix()
        eps = np.trace(v)** 2 / ddof1 * np.sum(np.sum(v * v, axis=1))
        corr_ddof1, corr_ddof2 = [np.maximum(d * eps, 1.) for d in \
                                                            (ddof1, ddof2)]
        p_corr = f(corr_ddof1, corr_ddof2).sf(fval)

    # Create output dataframe
    aov = pd.DataFrame({'Effect': within,
                        'ddof1': ddof1,
                        'ddof2': ddof2,
                        'F': fval,
                        'p_unc': p_unc,
                        'sphericity': sphericity
                        }, index=[0])
    if correction:
        aov['p-GG-corr'] = p_corr
        aov['W-Mauchly'] = W_mauchly
        aov['p-Mauchly'] = p_mauchly

    return aov