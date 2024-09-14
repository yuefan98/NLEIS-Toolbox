# import warnings
# from scipy.linalg import inv
# from scipy.optimize import basinhopping

import numpy as np
from scipy.optimize import curve_fit
from impedance.models.circuits.elements import circuit_elements, \
    get_element_from_name
from impedance.models.circuits.fitting import check_and_eval
from .fitting import set_default_bounds, buildCircuit, extract_circuit_elements
from scipy.optimize import minimize
import warnings

# Customize warning format (here, simpler and just the message)
warnings.formatwarning = lambda message, category, filename, lineno, \
    line=None: f'{category.__name__}: {message}\n'

ints = '0123456789'


def data_processing(f, Z1, Z2, max_f=10):
    '''

    Simple data processing function for EIS and 2nd-NLEIS simultaneously.

    Parameters
    ----------
    f : numpy array
        Frequencies

    Z1 : numpy array of dtype 'complex128'
        EIS data
    Z2 : numpy array of dtype 'complex128'
        2nd NLEIS data

    max_f: float
        The the maximum frequency of interest for 2nd-NLEIS

    Returns
    -------
    The processed EIS and 2nd-NLEIS data

    f : numpy array
        Frequencies that removes high frequency inductance

    Z1 : numpy array of dtype 'complex128'
        EIS data that removes the high frequency inductance

    Z2 : numpy array of dtype 'complex128'
        2nd-NLEIS data that has the same frequency range as Z1

    f2_truncated : numpy array
        Frequencies that removes high frequency inductance and less
        than the maximum measurable frequency for 2nd-NLEIS

    Z2_truncated : numpy array of dtype 'complex128'
        2nd-NLEIS data that has the same frequency range as f2_truncated

    '''
    mask = np.array(Z1.imag) < 0
    f = f[mask]
    Z1 = Z1[mask]
    Z2 = Z2[mask]
    mask1 = np.array(f) < max_f
    f2_truncated = f[mask1]
    Z2_truncated = Z2[mask1]
    return (f, Z1, Z2, f2_truncated, Z2_truncated)


def simul_fit(frequencies, Z1, Z2, circuit_1, circuit_2, edited_circuit,
              initial_guess, constants_1={}, constants_2={},
              bounds=None, opt='max', cost=0.5, max_f=10, param_norm=True,
              positive=True, **kwargs):
    """ Main function for the simultaneous fitting of EIS and NLEIS edata.

    By default, this function uses `scipy.optimize.curve_fit
    <https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.curve_fit.html>`_
    to fit the equivalent circuit.

    Parameters
    ----------
    frequencies : numpy array
        Frequencies
    Z1 : numpy array of dtype 'complex128'
        EIS data
    Z2 : numpy array of dtype 'complex128'
        2nd-NLEIS data

    circuit_1 : string
        String defining the EIS equivalent circuit to be fit
    circuit_2 : string
        String defining the 2nd-NLEIS equivalent circuit to be fit

    initial_guess : list of floats
        Initial guesses for the fit parameters

    constants : dictionary, optional
        Parameters and their values to hold constant during fitting
        (e.g. {"RO": 0.1}). Defaults to {}

    bounds : 2-tuple of array_like, optional
        Lower and upper bounds on parameters. Defaults to bounds on all
        parameters of 0 and np.inf,
        Exceptions:
        the CPE alpha  has an upper bound of 1,
        symmetry parameter (ε) for 2nd-NLEIS
        has bounds between -0.5 to 0.5
        curvature parameter (κ) for 2nd-NLEIS
        has bounds between -np.inf to np.inf

    opt : str, optional
        Default is max normalization 'max'.
        Negative Log-Likelihood is also supported as 'neg'.
        'max' is currently outperform 'neg'

    cost : float, default = 0.5
        cost function: cost > 0.5 means more weight on EIS while cost < 0.5
        means more weight on 2nd-NLEIS

    max_f: int
        The the maximum frequency of interest for 2nd-NLEIS

    positive : bool, optional
        Defaults to True to eliminate high frequency inductance

    param_norm : bool, optional
         Defaults to True for better convergence
         when customized bounds is supported

    kwargs :
        Keyword arguments passed to scipy.optimize.curve_fit

    Returns
    -------
    p_values : list of floats
        best fit parameters for EIS and 2nd-NLEIS data

    p_errors : list of floats
        one standard deviation error estimates for fitting parameters

    """
    # Todo improve the the negtive loglikelihood,
    # the code works fine for RC but not porous electrode

    # set upper and lower bounds on a per-element basis
    if bounds is None:
        combined_constant = constants_2.copy()
        combined_constant.update(constants_1)
        bounds = set_default_bounds(
            edited_circuit, constants=combined_constant)
        ub = np.ones(len(bounds[1]))
    else:
        if param_norm:
            inf_in_bounds = np.any(np.isinf(bounds[0])) \
                or np.any(np.isinf(bounds[1]))
            if inf_in_bounds:
                lb = np.where(bounds[0] == -np.inf, -1e10, bounds[0])
                ub = np.where(bounds[1] == np.inf, 1e10, bounds[1])
                bounds = (lb, ub)
                warnings.warn("inf is detected in the bounds, "
                              "to enable parameter normalization, "
                              "the bounds has been capped at 1e10. "
                              "You can disable parameter normalization "
                              "by set param_norm to False .")
            # ub = bounds[1]
            bounds = bounds/ub
        else:
            ub = np.ones(len(bounds[1]))

    initial_guess = initial_guess/ub

    if positive:
        mask1 = np.array(Z1.imag) < 0
        frequencies = frequencies[mask1]
        Z1 = Z1[mask1]
        Z2 = Z2[mask1]
        mask2 = np.array(frequencies) < max_f
        Z2 = Z2[mask2]
    else:
        mask2 = np.array(frequencies) < max_f
        Z2 = Z2[mask2]

    Z1stack = np.hstack([Z1.real, Z1.imag])
    Z2stack = np.hstack([Z2.real, Z2.imag])
    Zstack = np.hstack([Z1stack, Z2stack])
    # weighting scheme for fitting
    if opt == 'max':
        if 'maxfev' not in kwargs:
            kwargs['maxfev'] = 1e5
        if 'ftol' not in kwargs:
            kwargs['ftol'] = 1e-13
        Z1max = max(np.abs(Z1))
        Z2max = max(np.abs(Z2))

        sigma1 = np.ones(len(Z1stack))*Z1max/(cost**0.5)
        sigma2 = np.ones(len(Z2stack))*Z2max/((1-cost)**0.5)
        kwargs['sigma'] = np.hstack([sigma1, sigma2])

        popt, pcov = curve_fit(
            wrapCircuit_simul(edited_circuit, circuit_1, constants_1,
                              circuit_2, constants_2,
                              ub, max_f), frequencies, Zstack,
            p0=initial_guess, bounds=bounds, **kwargs)

    # Calculate one standard deviation error estimates for fit parameters,
    # defined as the square root of the diagonal of the covariance matrix.
    # https://stackoverflow.com/a/52275674/5144795
    # and the following for the bounded and normalized case
    # https://stackoverflow.com/questions/14854339/in-scipy-how-and-why-does-curve-fit-calculate-the-covariance-of-the-parameter-es
        perror = np.sqrt(np.diag(ub*pcov*ub.T))

        return popt*ub, perror
    if opt == 'neg':
        # This method does not provides converge solution
        # for porous electrode model under current development
        bounds = tuple(tuple((bounds[0][i], bounds[1][i]))
                       for i in range(len(bounds[0])))

        res = minimize(
            wrapNeg_log_likelihood(frequencies, Z1, Z2, edited_circuit,
                                   circuit_1, constants_1,
                                   circuit_2, constants_2,
                                   ub, max_f, cost=cost),
            x0=initial_guess, bounds=bounds, **kwargs)

        return (res.x*ub, None)


def wrapNeg_log_likelihood(frequencies, Z1, Z2, edited_circuit,
                           circuit_1, constants_1,
                           circuit_2, constants_2, ub, max_f=10, cost=0.5):
    ''' wraps function so we can pass the circuit string
    for negtive log likelihood optimization'''

    def wrappedNeg_log_likelihood(parameters):
        """ returns a stacked array of real and imaginary impedance
        components

        Parameters
        ----------
        frequencies: list of floats
        Z1: EIS data
        Z2: NLEIS data
        circuit_1 : string
        constants_1 : dict
        circuit_2 : string
        constants_2 : dict
        ub : list of floats upper bound if bounds are provided
        max_f: int
        parameters : list of floats

        Returns
        -------
        array of floats

        """
        f1 = frequencies
        mask = np.array(frequencies) < max_f
        f2 = frequencies[mask]
        x1, x2 = wrappedImpedance(edited_circuit,
                                  circuit_1, constants_1, circuit_2,
                                  constants_2, f1, f2, parameters*ub)
        # Z1max = max(np.abs(Z1))
        # Z2max = max(np.abs(Z2))
        # log1 = np.log(sum(((Z1.real-x1.real)/Z1max)**2))
        # +np.log(sum(((Z1.imag-x1.imag)/Z1max)**2))
        # log2 = np.log(sum(((Z2.real-x2.real)/Z2max)**2))
        # +np.log(sum(((Z2.imag-x2.imag)/Z2max)**2))
        log1 = np.log(sum(((Z1-x1))**2))
        log2 = np.log(sum(((Z2-x2))**2))
        return (cost*log1+(1-cost)*log2)
    return wrappedNeg_log_likelihood


def wrapCircuit_simul(edited_circuit, circuit_1, constants_1, circuit_2,
                      constants_2, ub, max_f=10):
    """ wraps function so we can pass the circuit string
    for simultaneous fitting """
    def wrappedCircuit_simul(frequencies, *parameters):
        """ returns a stacked array of real and imaginary impedance
        components

        Parameters
        ----------
        circuit_1 : string
        constants_1 : dict
        circuit_2 : string
        constants_2 : dict
        max_f: int
        parameters : list of floats
        frequencies : list of floats

        Returns
        -------
        array of floats

        """

        f1 = frequencies
        mask = np.array(frequencies) < max_f
        f2 = frequencies[mask]
        x1, x2 = wrappedImpedance(edited_circuit,
                                  circuit_1, constants_1,
                                  circuit_2, constants_2,
                                  f1, f2, parameters*ub)

        y1_real = np.real(x1)
        y1_imag = np.imag(x1)
        y1_stack = np.hstack([y1_real, y1_imag])
        y2_real = np.real(x2)
        y2_imag = np.imag(x2)
        y2_stack = np.hstack([y2_real, y2_imag])

        return np.hstack([y1_stack, y2_stack])
    return wrappedCircuit_simul


def wrappedImpedance(edited_circuit, circuit_1, constants_1, circuit_2,
                     constants_2, f1, f2, parameters):
    '''

    Parameters
    ----------
    circuit_1 : string
        EIS circuit string
    constants_1 : dict
        constant for EIS string.
    circuit_2 : string
        2nd-NLEIS circuit string
    constants_2 : dict
        constant for EIS string.

    f1 : list of floats
        frequency range for EIS
    f2 : list of floats
        frequency range for 2nd-NLEIS
    parameters : list of floats
        full parameters based on edited string.

    Returns
    -------
    x1
        calculated EIS (Z1)
    x2
        calculated 2nd-NLEIS (Z2)

    '''

    p1, p2 = individual_parameters(
        edited_circuit, parameters, constants_1, constants_2)

    x1 = eval(buildCircuit(circuit_1, f1, *p1,
                           constants=constants_1, eval_string='',
                           index=0)[0],
              circuit_elements)
    x2 = eval(buildCircuit(circuit_2, f2, *p2,
                           constants=constants_2, eval_string='',
                           index=0)[0],
              circuit_elements)
    return (x1, x2)


def individual_parameters(edited_circuit,
                          parameters, constants_1, constants_2):
    '''

    Parameters
    ----------
    edited_circuit : string
        Edited circuit string.
        For example, if EIS string: L0-R0-TDS0-TDS1
        2nd-NLEIS string: d(TDSn0-TDSn1).
        Then the edited str is L0-R0-TDSn0-TDSn1

    parameters : list of floats
        full parameters based on edited string.
    constants_1 : dict
        constant for EIS string.
    constants_2 : dict
        constants for 2nd-NLEIS string.

    Returns
    -------
    p1
        parameters for EIS.
    p2
        parameters for 2nd-NLEIS.

    '''

    if edited_circuit == '':
        return [], []
    parameters = list(parameters)
    elements_1 = extract_circuit_elements(edited_circuit)
    p1 = []
    p2 = []
    index = 0
    # Parse elements and store values
    for elem in elements_1:

        raw_elem = get_element_from_name(elem)
        nleis_elem_number = check_and_eval(raw_elem).num_params
        # this might be improvable, but depends on
        # how we want to define the name
        if (elem[0] == 'T' or elem[0:2] == 'RC') and 'n' in elem:
            # check for nonlinear element
            eis_elem_number = check_and_eval(raw_elem[0:-1]).num_params

        else:
            eis_elem_number = nleis_elem_number

        for j in range(nleis_elem_number):
            if eis_elem_number > 1:
                if j < eis_elem_number:
                    eis_current_elem = elem.replace("n", "") + '_{}'.format(j)
                else:
                    eis_current_elem = None
                nleis_current_elem = elem + '_{}'.format(j)

            else:
                eis_current_elem = elem
                nleis_current_elem = elem
            if eis_current_elem in constants_1.keys():
                continue
            elif (nleis_current_elem in constants_2.keys() and
                  eis_current_elem not in constants_1.keys()):
                continue
            else:
                if eis_elem_number == 1:
                    p1.append(parameters[index])

                elif eis_elem_number > 1 and j < eis_elem_number:
                    p1.append(parameters[index])
                    if nleis_elem_number > eis_elem_number:
                        p2.append(parameters[index])
                else:
                    p2.append(parameters[index])

                index += 1

    return p1, p2
