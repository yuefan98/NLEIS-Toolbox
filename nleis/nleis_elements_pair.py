import numpy as np
from scipy.special import iv
from scipy import constants
from impedance.models.circuits.elements import circuit_elements, \
    ElementError, OverwriteError

F = constants.physical_constants['Faraday constant'][0]
R = constants.R
T = 298.15

# element function adopted from impedance.py for better documentation


def element(num_params, units, overwrite=False):
    """

    decorator to store metadata for a circuit element

    Parameters
    ----------
    num_params : int
        number of parameters for an element
    units : list of str
        list of units for the element parameters
    overwrite : bool (default False)
        if true, overwrites any existing element; if false,
        raises OverwriteError if element name already exists.

    """

    def decorator(func):
        def wrapper(p, f):
            typeChecker(p, f, func.__name__, num_params)
            return func(p, f)

        wrapper.num_params = num_params
        wrapper.units = units
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__

        global circuit_elements
        if func.__name__ in ["s", "p"]:
            raise ElementError("cannot redefine elements 's' (series)" +
                               "or 'p' (parallel)")
        elif func.__name__ in circuit_elements and not overwrite:
            raise OverwriteError(
                f"element {func.__name__} already exists. " +
                "If you want to overwrite the existing element," +
                "use `overwrite=True`."
            )
        else:
            circuit_elements[func.__name__] = wrapper

        return wrapper

    return decorator


def d(difference):
    '''
    This function calculates the impedance difference between two electrodes
    In a two electrode cell, subtract the positive electrode 2nd-NLEIS from
    the negative electrode 2nd-NLEIS to get the cell response.

    Notes
    -----

    .. math::

        Z_2 = Z_2^{+} - Z_2^{-}

    '''

    z = len(difference[0])*[0 + 0*1j]
    z += difference[0]
    z += -difference[-1]
    return z


# manually add difference (d) operators to circuit elements w/o metadata
circuit_elements['d'] = d


@element(num_params=2, units=['Ohm', 'F'])
def RCO(p, f):
    """

    EIS: Randles circuit (charge transfer only)

    Notes
    -----

    .. math::

        \\tilde{Z_1} = \\frac{R_{ct}}{1 + \\omega^{*}  j}

    and

    .. math::

        \\omega^{*} = \\omega R_{ct} C_{dl}


    **Parameters:**

    .. math::

        p[0] = R_{ct}; \\;
        p[1] = C_{dl}; \\;

    """
    ω = np.array(f)*2*np.pi
    Rct, Cdl = p[0], p[1]

    ω_star = ω*Rct*Cdl

    return Rct / (1 + ω_star*1j)


@element(num_params=3, units=['Ohm', 'F', ''])
def RCOn(p, f):
    '''

    2nd-NLEIS: Nonlinear Randles circuit
    (charge transfer only) from Ji et al. [1]

    Notes
    -----

    .. math::
        \\tilde{Z_2} = \\frac{-\\varepsilon f R_{ct}^2}
        {1 + 4\\omega^{*}  j - 5{\\omega^{*}}^2 - 2{\\omega^{*}}^3 j}

    and

    .. math::

        \\omega^{*} = \\omega R_{ct} C_{dl}


    **Parameters:**

    .. math::

        p[0] = R_{ct}; \\;
        p[1] = C_{dl}; \\;
        p[2] = ε; \\;

    [1] Y. Ji, D.T. Schwartz,
    Second-Harmonic Nonlinear Electrochemical Impedance Spectroscopy:
    I. Analytical theory and equivalent circuit representations
    for planar and porous electrodes.
    J. Electrochem. Soc. (2023). `doi: 10.1149/1945-7111/ad15ca
    <https://doi.org/10.1149/1945-7111/ad15ca>`_.

    '''
    ω = np.array(f)*2*np.pi
    Rct, Cdl, ε = p[0], p[1], p[2]

    ω_star = ω*Rct*Cdl

    return -ε*F/(R*T)*Rct**2 / (1 + 4*ω_star*1j - 5*ω_star**2 - 2*ω_star**3*1j)


@element(num_params=4, units=['Ohms', 'F', 'Ohms', 's'])
def RCD(p, f):
    '''

    EIS: Randles circuit with diffusion
    in a bounded thin film electrode from Ji et al. [1]

    Notes
    -----

    .. math::
        \\tilde{Z_1} = \\frac{R_{ct}}{\\frac{R_{ct}}
        {R_{ct} + \\tilde{Z}_{D,1}} + j\\omega^{*}}

    and

    .. math::

        \\omega^{*} = \\omega R_{ct} C_{dl}

    and

    .. math::

        Z_{D,1} = \\frac{A_w \\coth\\left(\\sqrt{j\\omega\\tau}
        \\right)}{\\sqrt{j\\omega\\tau}}

    **Parameters:**

    .. math::

        p[0] = R_{ct}; \\;
        p[1] = C_{dl}; \\;
        p[2] = A_{w}; \\;
        p[3] = τ; \\;

    [1] Y. Ji, D.T. Schwartz,
    Second-Harmonic Nonlinear Electrochemical Impedance Spectroscopy:
    I. Analytical theory and equivalent circuit representations
    for planar and porous electrodes.
    J. Electrochem. Soc. (2023). `doi: 10.1149/1945-7111/ad15ca
    <https://doi.org/10.1149/1945-7111/ad15ca>`_.

    '''
    omega = np.array(f)*2*np.pi
    Rct, Cdl, Aw, τd = p[0], p[1], p[2], p[3]

    Zd = Aw/(np.sqrt(1j*omega*τd)*np.tanh(np.sqrt(1j*omega*τd)))
    tau = omega*Rct*Cdl
    Z = Rct/(Rct/(Rct+Zd)+1j*tau)
    return (Z)


@element(num_params=6, units=['Ohms', 'F', 'Ohms', 's', '1/V', ''])
def RCDn(p, f):
    '''

    2nd-NLEIS: Nonlinear Randles circuit with diffusion
    in a bounded thin film electrode from Ji et al. [1]

    Notes
    -----

    .. math::

        \\tilde{Z_2} = \\frac{R_{ct}}{\\left(j2\\omega^{*}
        + \\frac{R_{ct}}{\\tilde{Z}_{D,2} + R_{ct}}\\right)}
        \\frac{\\left[ \\kappa
        \\left( \\frac{\\tilde{Z}_{D,1}}{\\tilde{Z}_{D,1}
        + R_{ct}} \\right)^2 - \\varepsilon f
        \\left( \\frac{R_{ct}}{\\tilde{Z}_{D,1}
        + R_{ct}} \\right)^2 \\right]}{\\tilde{Z}_{D,2} + R_{ct}}
        \\left( \\frac{R_{ct}}{\\frac{R_{ct}}{R_{ct}
        + \\tilde{Z}_{D,1}} + j\\omega^{*}} \\right)^2

    and

    .. math::

        \\omega^{*} = \\omega R_{ct} C_{dl}

    and

    .. math::

        Z_{D,1} = \\frac{A_w \\coth\\left(\\sqrt{j\\omega\\tau}
        \\right)}{\\sqrt{j\\omega\\tau}}

    and

    .. math::

        Z_{D,2} = \\frac{A_w \\coth\\left(\\sqrt{j2\\omega\\tau}
        \\right)}{\\sqrt{j2\\omega\\tau}}


    **Parameters:**

    .. math::
        p[0] = R_{ct}; \\;
        p[1] = C_{dl}; \\;
        p[2] = A_{w}; \\;
        p[3] = τ; \\;
        p[4] = κ; \\;
        p[5] = ε; \\;

    [1] Y. Ji, D.T. Schwartz,
    Second-Harmonic Nonlinear Electrochemical Impedance Spectroscopy:
    I. Analytical theory and equivalent circuit representations
    for planar and porous electrodes.
    J. Electrochem. Soc. (2023). `doi: 10.1149/1945-7111/ad15ca
    <https://doi.org/10.1149/1945-7111/ad15ca>`_.

    '''

    omega = np.array(f)*2*np.pi
    Rct, Cdl, Aw, τd, κ, e = p[0], p[1], p[2], p[3], p[4], p[5]

    Zd1 = Aw/(np.sqrt(1j*omega*τd)*np.tanh(np.sqrt(1j*omega*τd)))
    Zd2 = Aw/(np.sqrt(1j*2*omega*τd)*np.tanh(np.sqrt(1j*2*omega*τd)))

    f = 96485.3321233100184/(8.31446261815324*298)

    tau = omega*Rct*Cdl
    y1 = Rct/(Zd1+Rct)
    y2 = (Zd1/(Zd1+Rct))

    Z1 = Rct/(y1+1j*tau)
    const = ((Rct*κ*y2**2)-Rct*e*f*y1**2)/(Zd2+Rct)

    Z2 = (const*Z1**2)/(2*tau*1j+Rct/(Zd2+Rct))

    return (Z2)


@element(num_params=4, units=['Ohms', 'F', 'Ohms', 's'])
def RCS(p, f):
    '''

    EIS: Randles circuit with diffusion
    diffusion into a spherical electrode from Ji et al. [1]

    Notes
    -----

    .. math::
        \\tilde{Z_1} = \\frac{R_{ct}}{\\frac{R_{ct}}
        {R_{ct} + \\tilde{Z}_{D,1}} + j\\omega^{*}}

    and

    .. math::

        \\omega^{*} = \\omega R_{ct} C_{dl}

    and

    .. math::

        Z_{D,1} = \\frac{A_{w} \\tanh\\left( \\sqrt{j\\omega\\tau}
          \\right)}{\\sqrt{j\\omega\\tau}
            - \\tanh\\left( \\sqrt{j\\omega\\tau} \\right)}


    **Parameters:**

    .. math::

        p[0] = R{ct}; \\;
        p[1] = C_{dl}; \\;
        p[2] = A_{w}; \\;
        p[3] = τ; \\;

    [1] Y. Ji, D.T. Schwartz,
    Second-Harmonic Nonlinear Electrochemical Impedance Spectroscopy:
    I. Analytical theory and equivalent circuit representation
    for planar and porous electrodes.
    J. Electrochem. Soc. (2023). `doi: 10.1149/1945-7111/ad15ca
    <https://doi.org/10.1149/1945-7111/ad15ca>`_.

    '''
    omega = np.array(f)*2*np.pi
    Rct, Cdl, Aw, τd = p[0], p[1], p[2], p[3]

    Zd = Aw*np.tanh(np.sqrt(1j*omega*τd)) / \
        (np.sqrt(1j*omega*τd)-np.tanh(np.sqrt(1j*omega*τd)))

    tau = omega*Rct*Cdl
    Z = Rct/(Rct/(Rct+Zd)+1j*tau)
    return (Z)


@element(num_params=6, units=['Ohms', 'F', 'Ohms', 's', '1/V', ''])
def RCSn(p, f):
    '''

    2nd-NLEIS: Nonlinear Randles circuit with diffusion
    diffusion into a spherical electrode from Ji et al. [1]

    Notes
    -----

    .. math::

        \\tilde{Z_2} = \\frac{R_{ct}}{\\left(j2\\omega^{*}
        + \\frac{R_{ct}}{\\tilde{Z}_{D,2} + R_{ct}}\\right)}
        \\frac{\\left[ \\kappa
        \\left( \\frac{\\tilde{Z}_{D,1}}{\\tilde{Z}_{D,1}
        + R_{ct}} \\right)^2 - \\varepsilon f
        \\left( \\frac{R_{ct}}{\\tilde{Z}_{D,1}
        + R_{ct}} \\right)^2 \\right]}{\\tilde{Z}_{D,2} + R_{ct}}
        \\left( \\frac{R_{ct}}{\\frac{R_{ct}}{R_{ct}
        + \\tilde{Z}_{D,1}} + j\\omega^{*}} \\right)^2

    and

    .. math::

        \\omega^{*} = \\omega R_{ct} C_{dl}

    and

    .. math::

        Z_{D,1} = Z_{D,1} = \\frac{A_{w} \\tanh\\left( \\sqrt{j\\omega\\tau}
          \\right)}{\\sqrt{j\\omega\\tau}
            - \\tanh\\left( \\sqrt{j\\omega\\tau} \\right)}

    and

    .. math::

        Z_{D,2} = \\frac{A_{w} \\tanh\\left( \\sqrt{j2\\omega\\tau}
          \\right)}{\\sqrt{j2\\omega\\tau}
            - \\tanh\\left( \\sqrt{j2\\omega\\tau} \\right)}


    **Parameters:**

    .. math::

        p[0] = R_{ct}; \\;
        p[1] = C_{dl}; \\;
        p[2] = A_{w}; \\;
        p[3] = τ; \\;
        p[4] = κ; \\;
        p[5] = ε; \\;

    [1] Y. Ji, D.T. Schwartz,
    Second-Harmonic Nonlinear Electrochemical Impedance Spectroscopy:
    I. Analytical theory and equivalent circuit representations
    for planar and porous electrodes.
    J. Electrochem. Soc. (2023). `doi: 10.1149/1945-7111/ad15ca
    <https://doi.org/10.1149/1945-7111/ad15ca>`_.

    '''

    omega = np.array(f)*2*np.pi
    Rct, Cdl, Aw, τd, κ, e = p[0], p[1], p[2], p[3], p[4], p[5]

    Zd1 = Aw*np.tanh(np.sqrt(1j*omega*τd)) / \
        (np.sqrt(1j*omega*τd)-np.tanh(np.sqrt(1j*omega*τd)))
    Zd2 = Aw*np.tanh(np.sqrt(1j*2*omega*τd)) / \
        (np.sqrt(1j*2*omega*τd)-np.tanh(np.sqrt(1j*2*omega*τd)))

    f = 96485.3321233100184/(8.31446261815324*298)

    tau = omega*Rct*Cdl
    y1 = Rct/(Zd1+Rct)
    y2 = (Zd1/(Zd1+Rct))

    Z1 = Rct/(y1+1j*tau)
    const = ((Rct*κ*y2**2)-Rct*e*f*y1**2)/(Zd2+Rct)

    Z2 = (const*Z1**2)/(2*tau*1j+Rct/(Zd2+Rct))

    return (Z2)


@element(num_params=3, units=['Ohms', 'Ohms', 'F'])
def TPO(p, f):
    '''

    EIS: Porous electrode with high conductivity matrix (charge transfer only)
    from Ji et al. [1]

    Notes
    -----

    .. math::

        Z_1 = \\frac{R_{\\text{pore}} \\coth(\\beta_1)}{\\beta_1}

    where

    .. math::

        \\beta_1 = \\left( j \\omega C_{\\text{dl}} R_{\\text{pore}} +
        \\frac{R_{\\text{pore}}}{R_{\\text{ct}}} \\right)^{\\frac{1}{2}}

    **Parameters:**

    .. math::

        p[0] = R_{pore}; \\;
        p[1] = R_{ct}; \\;
        p[2] = C_{dl}; \\;

    [1] Y. Ji, D.T. Schwartz,
    Second-Harmonic Nonlinear Electrochemical Impedance Spectroscopy:
    I. Analytical theory and equivalent circuit representations
    for planar and porous electrodes.
    J. Electrochem. Soc. (2023). `doi: 10.1149/1945-7111/ad15ca
    <https://doi.org/10.1149/1945-7111/ad15ca>`_.

    '''

    omega = 2*np.pi*np.array(f)

    Rpore, Rct, Cdl = p[0], p[1], p[2]

    beta = (1j*omega*Rpore*Cdl+Rpore/Rct)**(1/2)

    Z = Rpore/(beta*np.tanh(beta))
    return Z


@element(num_params=4, units=['Ohms', 'Ohms', 'F', ''])
def TPOn(p, f):
    """

    2nd-NLEIS: Porous electrode with high conductivity matrix
    (charge transfer only) from Ji et al. [1]

    Notes
    -----

    .. math::

        Z_2 = \\frac{ε f R_{\\text{pore}}^3}{R_{\\text{ct}}
        (\\beta_1 \\sinh(\\beta_1))^2}
        \\left[ \\left( \\frac{\\beta_1 \\sinh(2\\beta_1)}
        {\\beta_2(\\beta_2 - 2\\beta_1)
        (\\beta_2 + 2\\beta_1)} \\coth(\\beta_2) \\right) - \n
        \\left( \\frac{\\cosh(2\\beta_1)}{2(\\beta_2 - 2\\beta_1)
        (\\beta_2 + 2\\beta_1)} + \\frac{1}{2\\beta_2^2} \\right) \\right]

    where

    .. math::

        \\beta_1 = \\left( j \\omega C_{\\text{dl}} R_{\\text{pore}}
        + \\frac{R_{\\text{pore}}}{R_{\\text{ct}}} \\right)^{\\frac{1}{2}}

    and

    .. math::

        \\beta_2 = \\left( j 2\\omega C_{\\text{dl}} R_{\\text{pore}}
        + \\frac{R_{\\text{pore}}}{R_{\\text{ct}}} \\right)^{\\frac{1}{2}}

    **Parameters:**

    .. math::
        p[0] = R_{pore}; \\;
        p[1] = R_{ct}; \\;
        p[2] = C_{dl}; \\;
        p[3] = ε; \\;

    [1] Y. Ji, D.T. Schwartz,
    Second-Harmonic Nonlinear Electrochemical Impedance Spectroscopy:
    I. Analytical theory and equivalent circuit representations
    for planar and porous electrodes.
    J. Electrochem. Soc. (2023). `doi: 10.1149/1945-7111/ad15ca
    <https://doi.org/10.1149/1945-7111/ad15ca>`_.

    """

    omega = 2*np.pi*np.array(f)
    Rpore, Rct, Cdl, e = p[0], p[1], p[2], p[3]
    b1 = (1j*omega*Rpore*Cdl+Rpore/Rct)**(1/2)
    b2 = (1j*2*omega*Rpore*Cdl+Rpore/Rct)**(1/2)

    f = 96485.3321233100184/(8.31446261815324*298)
    sinh1 = []
    for x in b1:
        if x < 100:
            sinh1.append(np.sinh(x))
        else:
            sinh1.append(1e10)
    sinh2 = []
    cosh2 = []
    for x in b1:
        if x < 100:
            sinh2.append(np.sinh(2*x))
            cosh2.append(np.cosh(2*x))
        else:
            sinh2.append(1e10)
            cosh2.append(1e10)
    sinh3 = []
    cosh3 = []
    for x in b2:
        if x < 100:
            sinh3.append(np.sinh(x))
            cosh3.append(np.cosh(x))
        else:
            sinh3.append(1e10)
            cosh3.append(1e10)

    mf = ((Rpore**3)/Rct)*e*f/((b1*np.array(sinh1))**2)
    part1 = (b1/b2)*np.array(sinh2)/((b2**2-4*b1**2)*np.tanh(b2))
    part2 = -np.array(cosh2)/(2*(b2**2-4*b1**2))-1/(2*b2**2)
    Z = mf*(part1+part2)

    return Z


@element(num_params=5, units=['Ohms', 'Ohms', 'F', 'Ohms', 's'])
def TDP(p, f):
    """

    EIS: orous electrode with high conductivity matrix
    and planar diffusion into platelet-like particles from Ji et al. [1]

    Notes
    -----

    .. math::

        Z_1 = \\frac{R_{\\text{pore}} \\coth(\\beta_1^D)}{\\beta_1^D}

    where

    .. math::

        \\beta_1^D = \\left( j\\omega C_{\\text{dl}} R_{\\text{pore}}
        + \\frac{R_{\\text{pore}}}
        {Z_{D,1} + R_{\\text{ct}}} \\right)^{\\frac{1}{2}}

    and

    .. math::

        Z_{D,1} = \\frac{A_{w} \\coth\\left( \\sqrt{j\\omega\\tau}
        \\right)}{\\sqrt{j\\omega\\tau}}


    **Parameters:**

    .. math::

        p[0] = R_{pore}; \\;
        p[1] = R_{ct}; \\;
        p[2] = C_{dl}; \\;
        p[3] = A_{w}; \\;
        p[4] = τ; \\;


    [1] Y. Ji, D.T. Schwartz,
    Second-Harmonic Nonlinear Electrochemical Impedance Spectroscopy:
    I. Analytical theory and equivalent circuit representations
    for planar and porous electrodes.
    J. Electrochem. Soc. (2023). `doi: 10.1149/1945-7111/ad15ca
    <https://doi.org/10.1149/1945-7111/ad15ca>`_.

    """
    omega = 2*np.pi*np.array(f)
    Rpore, Rct, Cdl, Aw, τd = p[0], p[1], p[2], p[3], p[4]

    Zd = Aw/(np.sqrt(1j*omega*τd)*np.tanh(np.sqrt(1j*omega*τd)))

    beta = (1j*omega*Rpore*Cdl+Rpore/(Zd+Rct))**(1/2)
    Z = Rpore/(beta*np.tanh(beta))

    return Z


@element(num_params=7, units=['Ohms', 'Ohms', 'F', 'Ohms', 's', '1/V', ''])
def TDPn(p, f):
    """

    2nd-NLEIS: A macrohomogeneous porous electrode model with planar diffusion
    and zero solid resistivity from Ji et al. [1]

    Notes
    -----

    .. math::

        Z_2 = \\frac{ε f R_{\\text{pore}}^3}{R_{\\text{ct}}
        (\\beta_1^D \\sinh(\\beta_1^D))^2}
        \\left[ \\left( \\frac{\\beta_1^D \\sinh(2\\beta_1^D)}
        {\\beta_2^D(\\beta_2^D - 2\\beta_1^D)
        (\\beta_2^D + 2\\beta_1^D)} \\coth(\\beta_2^D) \\right) - \n
        \\left( \\frac{\\cosh(2\\beta_1^D)}{2(\\beta_2^D - 2\\beta_1^D)
        (\\beta_2^D + 2\\beta_1^D)} +
        \\frac{1}{2{\\beta_2^D}^2} \\right) \\right]

    where

    .. math::

        \\beta_1^D = \\left( j2\\omega C_{\\text{dl}} R_{\\text{pore}} +
        \\frac{R_{\\text{pore}}}{\\tilde{Z}_{D,1}
        + R_{\\text{ct}}} \\right)^{\\frac{1}{2}}

    and

    .. math::

        \\beta_2^D = \\left( j2\\omega C_{\\text{dl}} R_{\\text{pore}} +
        \\frac{R_{\text{pore}}}{\\tilde{Z}_{D,2}
        + R_{\\text{ct}}} \\right)^{\\frac{1}{2}}

    and

    .. math::

        Z_{D,1} = \\frac{A_{w} \\coth\\left( \\sqrt{j\\omega\\tau}
        \\right)}{\\sqrt{j\\omega\\tau}}

    and

    .. math::

        Z_{D,2} = \\frac{A_{w} \\coth\\left( \\sqrt{j2\\omega\\tau}
        \\right)}{\\sqrt{j2\\omega\\tau}}


    **Parameters:**

    .. math::
        p[0] = R_{pore}; \\;
        p[1] = R{ct}; \\;
        p[2] = C_{dl}; \\;
        p[3] = A_{w}; \\;
        p[4] = τ; \\;
        p[5] = κ; \\;
        p[6] = ε; \\;

    [1] Y. Ji, D.T. Schwartz,
    Second-Harmonic Nonlinear Electrochemical Impedance Spectroscopy:
    I. Analytical theory and equivalent circuit representations
    for planar and porous electrodes.
    J. Electrochem. Soc. (2023). `doi: 10.1149/1945-7111/ad15ca
    <https://doi.org/10.1149/1945-7111/ad15ca>`_.

    """

    omega = 2*np.pi*np.array(f)
    Rpore, Rct, Cdl, Aw, τd, κ, e = p[0], p[1], p[2], p[3], p[4], p[5], p[6]

    Zd1 = Aw/(np.sqrt(1j*omega*τd)*np.tanh(np.sqrt(1j*omega*τd)))
    Zd2 = Aw/(np.sqrt(1j*2*omega*τd)*np.tanh(np.sqrt(1j*2*omega*τd)))

    y1 = Rct/(Zd1+Rct)
    y2 = (Zd1/(Zd1+Rct))

    b1 = (1j*omega*Rpore*Cdl+Rpore/(Zd1+Rct))**(1/2)
    b2 = (1j*2*omega*Rpore*Cdl+Rpore/(Zd2+Rct))**(1/2)

    f = 96485.3321233100184/(8.31446261815324*298)
    sinh1 = []
    for x in b1:
        if x < 100:
            sinh1.append(np.sinh(x))
        else:
            sinh1.append(1e10)
    sinh2 = []
    cosh2 = []
    for x in b1:
        if x < 100:
            sinh2.append(np.sinh(2*x))
            cosh2.append(np.cosh(2*x))
        else:
            sinh2.append(1e10)
            cosh2.append(1e10)
    const = -((Rct*κ*y2**2)-Rct*e*f*y1**2)/(Zd2+Rct)
    mf = ((Rpore**3)*const/Rct)/((b1*np.array(sinh1))**2)
    part1 = (b1/b2)*np.array(sinh2)/((b2**2-4*b1**2)*np.tanh(b2))
    part2 = -np.array(cosh2)/(2*(b2**2-4*b1**2))-1/(2*b2**2)
    Z = mf*(part1+part2)

    return Z


@element(num_params=5, units=['Ohms', 'Ohms', 'F', 'Ohms', 's'])
def TDS(p, f):
    """

    EIS: porous electrode with high conductivity matrix and
    diffusion into spherical particles from Ji et al. [1]

    Notes
    -----

    .. math::

        Z_1 = \\frac{R_{\\text{pore}} \\coth(\\beta_1^D)}{\\beta_1^D}

    where

    .. math::

        \\beta_1^D = \\left( j\\omega C_{\\text{dl}} R_{\\text{pore}}
        + \\frac{R_{\\text{pore}}}
        {Z_{D,1} + R_{\\text{ct}}} \\right)^{\\frac{1}{2}}

    and

    .. math::

        Z_{D,1} = \\frac{A_{w} \\tanh\\left( \\sqrt{j\\omega\\tau}
        \\right)}{\\sqrt{j\\omega\\tau}
        - \\tanh\\left( \\sqrt{j\\omega\\tau} \\right)}


    **Parameters:**

    .. math::

        p[0] = Rpore; \\;
        p[1] = Rct; \\;
        p[2] = Cdl; \\;
        p[3] = Aw; \\;
        p[4] = τd; \\;

    [1] Y. Ji, D.T. Schwartz,
    Second-Harmonic Nonlinear Electrochemical Impedance Spectroscopy:
    I. Analytical theory and equivalent circuit representations
    for planar and porous electrodes.
    J. Electrochem. Soc. (2023). `doi: 10.1149/1945-7111/ad15ca
    <https://doi.org/10.1149/1945-7111/ad15ca>`_.


    """
    omega = 2*np.pi*np.array(f)
    Rpore, Rct, Cdl, Aw, τd = p[0], p[1], p[2], p[3], p[4]

    Zd = Aw*np.tanh(np.sqrt(1j*omega*τd)) / \
        (np.sqrt(1j*omega*τd)-np.tanh(np.sqrt(1j*omega*τd)))

    beta = (1j*omega*Rpore*Cdl+Rpore/(Zd+Rct))**(1/2)
    Z = Rpore/(beta*np.tanh(beta))
    return Z


@element(num_params=7, units=['Ohms', 'Ohms', 'F', 'Ohms', 's', '1/V', ''])
def TDSn(p, f):
    """

    2nd-NLEIS: porous electrode with high conductivity matrix and
    diffusion into spherical particles from Ji et al. [1]

    Notes
    -----

    .. math::

        Z_2 = \\frac{ε f R_{\\text{pore}}^3}{R_{\\text{ct}}
        (\\beta_1^D \\sinh(\\beta_1^D))^2}
        \\left[ \\left( \\frac{\\beta_1^D \\sinh(2\\beta_1^D)}
        {\\beta_2^D(\\beta_2^D - 2\\beta_1^D)
        (\\beta_2^D + 2\\beta_1^D)} \\coth(\\beta_2^D) \\right) - \n
        \\left( \\frac{\\cosh(2\\beta_1^D)}{2(\\beta_2^D - 2\\beta_1^D)
        (\\beta_2^D + 2\\beta_1^D)} +
        \\frac{1}{2{\\beta_2^D}^2} \\right) \\right]

    where

    .. math::

        \\beta_1^D = \\left( j2\\omega C_{\\text{dl}} R_{\\text{pore}} +
        \\frac{R_{\\text{pore}}}{\\tilde{Z}_{D,1}
        + R_{\\text{ct}}} \\right)^{\\frac{1}{2}}

    and

    .. math::

        \\beta_2^D = \\left( j2\\omega C_{\\text{dl}} R_{\\text{pore}} +
        \\frac{R_{\text{pore}}}{\\tilde{Z}_{D,2}
        + R_{\\text{ct}}} \\right)^{\\frac{1}{2}}

    and

    .. math::

        Z_{D,1} = \\frac{A_{w} \\tanh\\left( \\sqrt{j\\omega\\tau}
        \\right)}{\\sqrt{j\\omega\\tau}
        - \\tanh\\left( \\sqrt{j\\omega\\tau} \\right)}

    and

    .. math::

        Z_{D,2} = \\frac{A_{w} \\tanh\\left( \\sqrt{j2\\omega\\tau}
        \\right)}{\\sqrt{j2\\omega\\tau}
        - \\tanh\\left( \\sqrt{j2\\omega\\tau} \\right)}

    **Parameters:**

    .. math::

        p[0] = Rpore; \\;
        p[1] = Rct; \\;
        p[2] = Cdl; \\;
        p[3] = Aw; \\;
        p[4] = τ; \\;
        p[5] = κ; \\;
        p[6] = ε; \\;

    [1] Y. Ji, D.T. Schwartz,
    Second-Harmonic Nonlinear Electrochemical Impedance Spectroscopy:
    I. Analytical theory and equivalent circuit representations
    for planar and porous electrodes.
    J. Electrochem. Soc. (2023). `doi: 10.1149/1945-7111/ad15ca
    <https://doi.org/10.1149/1945-7111/ad15ca>`_.


    """

    omega = 2*np.pi*np.array(f)
    Rpore, Rct, Cdl, Aw, τd, κ, e = p[0], p[1], p[2], p[3], p[4], p[5], p[6]
    Zd1 = Aw*np.tanh(np.sqrt(1j*omega*τd)) / \
        (np.sqrt(1j*omega*τd)-np.tanh(np.sqrt(1j*omega*τd)))
    Zd2 = Aw*np.tanh(np.sqrt(1j*2*omega*τd)) / \
        (np.sqrt(1j*2*omega*τd)-np.tanh(np.sqrt(1j*2*omega*τd)))

    y1 = Rct/(Zd1+Rct)
    y2 = (Zd1/(Zd1+Rct))

    b1 = (1j*omega*Rpore*Cdl+Rpore/(Zd1+Rct))**(1/2)
    b2 = (1j*2*omega*Rpore*Cdl+Rpore/(Zd2+Rct))**(1/2)

    f = 96485.3321233100184/(8.31446261815324*298)
    sinh1 = []
    for x in b1:
        if x < 100:
            sinh1.append(np.sinh(x))
        else:
            sinh1.append(1e10)
    sinh2 = []
    cosh2 = []
    for x in b1:
        if x < 100:
            sinh2.append(np.sinh(2*x))
            cosh2.append(np.cosh(2*x))
        else:
            sinh2.append(1e10)
            cosh2.append(1e10)
    const = -((Rct*κ*y2**2)-Rct*e*f*y1**2)/(Zd2+Rct)
    mf = ((Rpore**3)*const/Rct)/((b1*np.array(sinh1))**2)
    part1 = (b1/b2)*np.array(sinh2)/((b2**2-4*b1**2)*np.tanh(b2))
    part2 = -np.array(cosh2)/(2*(b2**2-4*b1**2))-1/(2*b2**2)
    Z = mf*(part1+part2)

    return Z


@element(num_params=5, units=['Ohms', 'Ohms', 'F', 'Ohms', 's'])
def TDC(p, f):
    """

    EIS: porous electrode with high conductivity matrix and
    diffusion into cylindrical particles from Ji et al. [1]

    Notes
    -----

    .. math::

        Z_1 = \\frac{R_{\\text{pore}} \\coth(\\beta_1^D)}{\\beta_1^D}

    where

    .. math::

        \\beta_1^D = \\left( j\\omega C_{\\text{dl}} R_{\\text{pore}}
        + \\frac{R_{\\text{pore}}}
        {Z_{D,1} + R_{\\text{ct}}} \\right)^{\\frac{1}{2}}

    and

    .. math::

        Z_{D,1} = A_w \\frac{I_0\\left(\\sqrt{j \\omega \\tau}\\right)}
        {\\sqrt{j \\omega \\tau} I_1\\left(\\sqrt{j \\omega \\tau}\\right)}

    **Parameters:**

    .. math::
        p[0] = R_{pore}; \\;
        p[1] = R_{ct}; \\;
        p[2] = C_{dl}; \\;
        p[3] = A_{w}; \\;
        p[4] = τ; \\;

    [1] Y. Ji, D.T. Schwartz,
    Second-Harmonic Nonlinear Electrochemical Impedance Spectroscopy:
    I. Analytical theory and equivalent circuit representations
    for planar and porous electrodes.
    J. Electrochem. Soc. (2023). `doi: 10.1149/1945-7111/ad15ca
    <https://doi.org/10.1149/1945-7111/ad15ca>`_.

    """
    omega = 2*np.pi*np.array(f)
    Rpore, Rct, Cdl, Aw, τd = p[0], p[1], p[2], p[3], p[4]
    i01 = []
    i11 = []
    for x in np.sqrt(1j*omega*τd):
        if x < 100:
            i01.append(iv(0, x))
            i11.append(iv(1, x))
        else:
            i01.append(1e20)
            i11.append(1e20)
    Zd = Aw*np.array(i01)/(np.sqrt(1j*omega*τd)*np.array(i11))

    beta = (1j*omega*Rpore*Cdl+Rpore/(Zd+Rct))**(1/2)
    Z = Rpore/(beta*np.tanh(beta))
    return Z


@element(num_params=7, units=['Ohms', 'Ohms', 'F', 'Ohms', 's', '1/V', ''])
def TDCn(p, f):
    """

    2nd-NLEIS: porous electrode with high conductivity matrix and
    diffusion into cylindrical particles from Ji et al. [1]

    Notes
    -----

    .. math::

        Z_2 = \\frac{ε f R_{\\text{pore}}^3}{R_{\\text{ct}}
        (\\beta_1^D \\sinh(\\beta_1^D))^2}
        \\left[ \\left( \\frac{\\beta_1^D \\sinh(2\\beta_1^D)}
        {\\beta_2^D(\\beta_2^D - 2\\beta_1^D)
        (\\beta_2^D + 2\\beta_1^D)} \\coth(\\beta_2^D) \\right) - \n
        \\left( \\frac{\\cosh(2\\beta_1^D)}{2(\\beta_2^D - 2\\beta_1^D)
        (\\beta_2^D + 2\\beta_1^D)} +
        \\frac{1}{2{\\beta_2^D}^2} \\right) \\right]

    where

    .. math::

        \\beta_1^D = \\left( j2\\omega C_{\\text{dl}} R_{\\text{pore}} +
        \\frac{R_{\\text{pore}}}{\\tilde{Z}_{D,1}
        + R_{\\text{ct}}} \\right)^{\\frac{1}{2}}

    and

    .. math::

        \\beta_2^D = \\left( j2\\omega C_{\\text{dl}} R_{\\text{pore}} +
        \\frac{R_{\text{pore}}}{\\tilde{Z}_{D,2}
        + R_{\\text{ct}}} \\right)^{\\frac{1}{2}}

    and

    .. math::

        Z_{D,1} = A_w \\frac{I_0\\left(\\sqrt{j \\omega \\tau}\\right)}
        {\\sqrt{j \\omega \\tau} I_1\\left(\\sqrt{j \\omega \\tau}\\right)}

    and

    .. math::

        Z_{D,2} = A_w \\frac{I_0\\left(\\sqrt{j 2\\omega \\tau}\\right)}
        {\\sqrt{j 2\\omega \\tau} I_1\\left(\\sqrt{j 2\\omega \\tau}\\right)}

    **Parameters:**

    .. math::

        p[0] = R_{pore}; \\;
        p[1] = R_{ct}; \\;
        p[2] = C_{dl}; \\;
        p[3] = A_{w}; \\;
        p[4] = τ; \\;
        p[5] = κ; \\;
        p[6] = ε; \\;

    [1] Y. Ji, D.T. Schwartz,
    Second-Harmonic Nonlinear Electrochemical Impedance Spectroscopy:
    I. Analytical theory and equivalent circuit representations
    for planar and porous electrodes.
    J. Electrochem. Soc. (2023). `doi: 10.1149/1945-7111/ad15ca
    <https://doi.org/10.1149/1945-7111/ad15ca>`_.

    """

    omega = 2*np.pi*np.array(f)
    Rpore, Rct, Cdl, Aw, τd, κ, e = p[0], p[1], p[2], p[3], p[4], p[5], p[6]

    i01 = []
    i11 = []
    for x in np.sqrt(1j*omega*τd):
        if x < 100:
            i01.append(iv(0, x))
            i11.append(iv(1, x))
        else:
            i01.append(1e20)
            i11.append(1e20)
    i02 = []
    i12 = []
    for x in np.sqrt(1j*2*omega*τd):
        if x < 100:
            i02.append(iv(0, x))
            i12.append(iv(1, x))
        else:
            i02.append(1e20)
            i12.append(1e20)
    Zd1 = Aw*np.array(i01)/(np.sqrt(1j*omega*τd)*np.array(i11))
    Zd2 = Aw*np.array(i02)/(np.sqrt(1j*2*omega*τd)*np.array(i12))

    y1 = Rct/(Zd1+Rct)
    y2 = (Zd1/(Zd1+Rct))

    b1 = (1j*omega*Rpore*Cdl+Rpore/(Zd1+Rct))**(1/2)
    b2 = (1j*2*omega*Rpore*Cdl+Rpore/(Zd2+Rct))**(1/2)

    f = 96485.3321233100184/(8.31446261815324*298)
    sinh1 = []
    for x in b1:
        if x < 100:
            sinh1.append(np.sinh(x))
        else:
            sinh1.append(1e10)
    sinh2 = []
    cosh2 = []
    for x in b1:
        if x < 100:
            sinh2.append(np.sinh(2*x))
            cosh2.append(np.cosh(2*x))
        else:
            sinh2.append(1e10)
            cosh2.append(1e10)
    const = -((Rct*κ*y2**2)-Rct*e*f*y1**2)/(Zd2+Rct)
    mf = ((Rpore**3)*const/Rct)/((b1*np.array(sinh1))**2)
    part1 = (b1/b2)*np.array(sinh2)/((b2**2-4*b1**2)*np.tanh(b2))
    part2 = -np.array(cosh2)/(2*(b2**2-4*b1**2))-1/(2*b2**2)
    Z = mf*(part1+part2)

    return Z

# TLM Model #


@element(num_params=6, units=['Ohm', 'Ohm', 'F', 'Ohm', 'F', ''])
def TLM(p, f):
    """

    EIS： General discrete transmission line model built  Randles circuit

    Notes
    -----



    **Parameters:**

    .. math::

        p[0] = R_{pore}; \\;
        p[1] = R_{ct, bulk}; \\;
        p[2] = C_{dl, bulk}; \\;
        p[3] = R_{ct, surface}; \\;

    .. math::

        p[4] = C_{dl, surface}; \\;
        p[5] = N (\\text{number of circuit element}); \\;


    """

    N = int(p[5])
    frequencies = np.array(f)

    Rct = p[1]*N
    Cdl = p[2]/N
    Rpore = p[0]/N
    Rs = p[3]*N
    Cs = p[4]/N

    Z1b = RCO([Rct, Cdl], frequencies)
    Z1s = RCO([Rs, Cs], frequencies)
    Zran = Z1b + Z1s
    Req = Zran
    for i in range(1, N):

        Req_inv = (1/(Req+Rpore))+1/Zran
        Req = 1/Req_inv

    return (Req)
###


@element(num_params=8, units=['Ohm', 'Ohm', 'F', '', 'Ohm', 'F', '', ''])
def TLMn(p, f):
    """

    2nd-NLEIS: Second harmonic nonlinear discrete transmission line model
    built based on the nonlinear Randles circuit from Ji et al. [1]

    Notes
    -----

    .. math::


    **Parameters:**

    .. math::

        p[0] = R_{pore}; \\;
        p[1] = R_{ct,bulk}; \\;
        p[2] = C_{dl,bulk}; \\;
        p[3] = R_{ct,surface}; \\;

    .. math::

        p[4] = C_{dl,surface}; \\;
        p[5] = N (\\text{number of circuit element}); \\;
        p[6] = ε_{bulk}; \\;
        p[7] = ε_{surface}; \\;



    [1] Y. Ji, D.T. Schwartz,
    Second-Harmonic Nonlinear Electrochemical Impedance Spectroscopy:
    I. Analytical theory and equivalent circuit representations
    for planar and porous electrodes.
    J. Electrochem. Soc. (2023). `doi: 10.1149/1945-7111/ad15ca
    <https://doi.org/10.1149/1945-7111/ad15ca>`_.

    """
    I1 = mTi(p[0:6], f)  # calculate the current fraction (1st harmonic)

    N = int(p[5])
    frequencies = np.array(f)

    Rpore = p[0]/N
    Rct = p[1]*N
    Cdl = p[2]/N
    Rs = p[3]*N
    Cs = p[4]/N

    eb = p[6]
    es = p[7]
    f = 96485.3321233100184/(8.31446261815324*298)  # unit in 1/V
    Z1b = RCO([Rct, Cdl], frequencies)
    Z1s = RCO([Rs, Cs], frequencies)
    Z2b = RCOn([Rct, Cdl, eb], frequencies)
    Z2s = RCOn([Rs, Cs, es], frequencies)
    Z1b2t = RCO([Rct, Cdl], 2*frequencies)
    Z1s2t = RCO([Rs, Cs], 2*frequencies)
    Z1 = Z1b+Z1s
    Z2 = Z2b+Z2s
    Z12t = Z1b2t+Z1s2t
    if N == 1:
        return (Z2)

    if N == 2:
        sum1 = Z1**2/(2*Z1+Rpore)**2
        sum2 = (Z12t*Rpore+Rpore**2)/((2*Z12t+Rpore)*(2*Z1+Rpore))
        Z = (sum1+sum2)*Z2
        return (Z)
    Z = np.zeros((len(frequencies)), dtype=complex)
    for freq in range(0, len(frequencies)):
        Ii = I1[freq]

        A = np.arange(N-1, 0, -1)
        A1 = np.arange(N-1, 0, -1)

        for i in range(0, N-2):
            for j in range(0, N-1-i):
                A1[j] = A1[j]-1
            A = np.vstack((A, A1))
        A = A*Rpore
        A = np.append(A, np.zeros((N-1, 1)), axis=1)
        A = np.append(A, np.zeros((1, N)), axis=0)
        A2 = np.zeros((N-1, N))
        for i in range(0, N-1):
            A2[i, 0] += 1
            A2[i, N-1-i] -= 1
        A2 = np.vstack((A2, np.zeros(N)))
        A2 = A2*Z12t[freq]

        A3 = np.vstack((np.zeros((N-1, N)), np.ones(N)))

        Ax = A2+A+A3

        b = np.zeros((N, 1), dtype=complex)

        for i in range(0, N-1):
            b[i] = Ii[-1]**2-Ii[i]**2

        I2 = np.linalg.solve(Ax, -b*Z2[freq])
        Z[freq] = Z2[freq]*Ii[0]**2+I2[-1]*Z12t[freq]
    return (Z)


@element(num_params=6, units=['Ohm', 'Ohm', 'F', 'Ohm', 'F', ''])
def mTi(p, f):
    """

    EIS: current distribution of  discrete transmission line model
    built based on the  Randles circuit from Ji et al. [1]

    Notes
    -----

    .. math::



    **Parameters:**

    .. math::

        p[0] = R_{pore}; \\;
        p[1] = R_{ct,bulk}; \\;
        p[2] = C_{dl,bulk}; \\;
        p[3] = R_{ct,surface}; \\;

    .. math::

        p[4] = C_{dl,surface}; \\;
        p[5] = N (\\text{number of circuit element}); \\;


    [1] Y. Ji, D.T. Schwartz,
    Second-Harmonic Nonlinear Electrochemical Impedance Spectroscopy:
    I. Analytical theory and equivalent circuit representations
    for planar and porous electrodes.
    J. Electrochem. Soc. (2023). `doi: 10.1149/1945-7111/ad15ca
    <https://doi.org/10.1149/1945-7111/ad15ca>`_.

    """

    N = int(p[5])
    frequencies = np.array(f)

    Rct = p[1]*N
    Cdl = p[2]/N
    Rpore = p[0]/N
    Rs = p[3]*N
    Cs = p[4]/N
    Z1b = RCO([Rct, Cdl], frequencies)
    Z1s = RCO([Rs, Cs], frequencies)
    Zran = Z1b + Z1s
    Req = Zran
    for i in range(1, N):

        Req_inv = (1/(Req+Rpore))+1/Zran
        Req = 1/Req_inv

    Req = Req+Rpore

    I1 = np.zeros((len(frequencies), N), dtype=complex)
    for freq in range(0, len(frequencies)):
        b1 = np.ones(N)*Req[freq]

        A = np.identity(N)*Zran[freq]

        A1 = np.ones((N, N))*Rpore

        for i in range(0, N):

            A1[i, :] = A1[i, :]*(i+1)

            for j in range(0, i):

                A[i][j] = -(i-j)*Rpore

        A = A+A1

        b = b1

        I1[freq, :] = np.linalg.solve(A, b)
    return (I1)


@element(num_params=8, units=['Ohm', 'Ohm', 'F', 'Ohm', 's', 'Ohm', 'F', ''])
def TLMS(p, f):
    """

    EIS: General discrete transmission line model
    built based on the Randles circuit
    with spherical diffusion from Ji et al.[1]

    Notes
    -----

    .. math::



    **Parameters:**

    .. math::
        p[0] = R_{pore}; \\;
        p[1] = R_{ct,bulk}; \\;
        p[2] = C_{dl,bulk}; \\;
        p[3] = A_{w,bulk}; \\;
        p[4] = τ_{bulk}; \\;

    .. math::

        p[5] = R_{ct,surface}; \\;
        p[6] = C_{dl,surface}; \\;
        p[7] = N (\\text{number of circuit element}); \\;


    [1] Y. Ji, D.T. Schwartz,
    Second-Harmonic Nonlinear Electrochemical Impedance Spectroscopy:
    I. Analytical theory and equivalent circuit representations
    for planar and porous electrodes.
    J. Electrochem. Soc. (2023). `doi: 10.1149/1945-7111/ad15ca
    <https://doi.org/10.1149/1945-7111/ad15ca>`_.

    """

    N = int(p[7])
    frequencies = np.array(f)

    Rpore = p[0]/N
    Rct = p[1]*N
    Cdl = p[2]/N
    Aw = p[3]*N
    τd = p[4]
    Rs = p[5]*N
    Cs = p[6]/N

    Z1b = RCS([Rct, Cdl, Aw, τd], frequencies)

    Z1s = RCO([Rs, Cs], frequencies)
    Zran = Z1b + Z1s
    Req = Zran
    for i in range(1, N):

        Req_inv = (1/(Req+Rpore))+1/Zran
        Req = 1/Req_inv

    return (Req)


@element(num_params=11, units=['Ohm', 'Ohm', 'F', 'Ohm', 's', 'Ohm', 'F', '',
                               '1/V', '', ''])
def TLMSn(p, f):
    """

    2nd-NLEIS: Second harmonic nonlinear discrete transmission line model
    built based on the Randles circuit
    with spherical diffusion from Ji et al. [1]

    Notes
    -----

    .. math::



    **Parameters:**

    .. math::
        p[0] = R_{pore}; \\;
        p[1] = R_{ct,bulk}; \\;
        p[2] = C_{dl,bulk}; \\;
        p[3] = A_{w,bulk}; \\;
        p[4] = τ_{bulk}; \\;
        p[5] = R_{ct,surface}; \\;


    .. math::

        p[6] = C_{dl,surface}; \\;
        p[7] = N (\\text{number of circuit element}); \\;
        p[8] = κ_{bulk}; \\;

    .. math::
        p[9] = ε_{bulk}; \\;
        p[10] = ε_{surface}; \\;



    """
    I1 = mTiS(p[0:8], f)  # calculate the current fraction (1st harmonic)

    N = int(p[7])

    frequencies = np.array(f)

    Rpore = p[0]/N
    Rct = p[1]*N
    Cdl = p[2]/N
    Aw = p[3]*N
    τd = p[4]
    Rs = p[5]*N
    Cs = p[6]/N
    κ = p[8]
    eb = p[9]
    es = p[10]

    Z1b = RCS([Rct, Cdl, Aw, τd], frequencies)
    Z1s = RCO([Rs, Cs], frequencies)
    Z2b = RCSn([Rct, Cdl, Aw, τd, κ, eb], frequencies)
    Z2s = RCOn([Rs, Cs, es], frequencies)
    Z1b2t = RCS([Rct, Cdl, Aw, τd], 2*frequencies)
    Z1s2t = RCO([Rs, Cs], 2*frequencies)

    Z1 = Z1b+Z1s
    Z2 = Z2b+Z2s
    Z12t = Z1b2t+Z1s2t

    if N == 1:
        return (Z2)

    if N == 2:
        sum1 = Z1**2/(2*Z1+Rpore)**2
        sum2 = (Z12t*Rpore+Rpore**2)/((2*Z12t+Rpore)*(2*Z1+Rpore))
        Z = (sum1+sum2)*Z2
        return (Z)

    Z = np.zeros(len(frequencies), dtype=complex)
    for freq in range(0, len(frequencies)):
        Ii = I1[freq]

        A = np.arange(N-1, 0, -1)
        A1 = np.arange(N-1, 0, -1)

        for i in range(0, N-2):
            for j in range(0, N-1-i):
                A1[j] = A1[j]-1
            A = np.vstack((A, A1))
        A = A*Rpore
        A = np.append(A, np.zeros((N-1, 1)), axis=1)
        A = np.append(A, np.zeros((1, N)), axis=0)
        A2 = np.zeros((N-1, N))
        for i in range(0, N-1):
            A2[i, 0] += 1
            A2[i, N-1-i] -= 1
        A2 = np.vstack((A2, np.zeros(N)))
        A2 = A2*Z12t[freq]

        A3 = np.vstack((np.zeros((N-1, N)), np.ones(N)))

        Ax = A2+A+A3

        b = np.zeros((N, 1), dtype=complex)

        for i in range(0, N-1):
            b[i] = Ii[-1]**2-Ii[i]**2

        I2 = np.linalg.solve(Ax, -b*Z2[freq])
        Z[freq] = Z2[freq]*Ii[0]**2+I2[-1]*Z12t[freq]
        # Z[freq]=Z2[freq]*Ii[0]**2

    return (Z)


@element(num_params=8, units=['Ohm', 'Ohm', 'F', 'Ohm', 's', 'Ohm', 'F', ''])
def mTiS(p, f):
    """

    EIS: current distribution of nonlinear discrete transmission line model
    built based on the Randles circuit
    with spherical diffusion from Ji et al. [1]

    Notes
    -----

    .. math::

    **Parameters:**

    .. math::
        p[0] = R_{pore}; \\;
        p[1] = R_{ct,bulk}; \\;
        p[2] = C_{dl,bulk}; \\;
        p[3] = A_{w,bulk}; \\;
        p[4] = τ_{bulk}; \\;
        p[5] = R_{ct,surface}; \\;


    .. math::

        p[6] = C_{dl,surface}; \\;
        p[7] = N (\\text{number of circuit element}); \\;


    [1] Y. Ji, D.T. Schwartz,
    Second-Harmonic Nonlinear Electrochemical Impedance Spectroscopy:
    I. Analytical theory and equivalent circuit representations
    for planar and porous electrodes.
    J. Electrochem. Soc. (2023). `doi: 10.1149/1945-7111/ad15ca
    <https://doi.org/10.1149/1945-7111/ad15ca>`_.

    """
    N = int(p[7])
    frequencies = np.array(f)

    Rpore = p[0]/N
    Rct = p[1]*N
    Cdl = p[2]/N
    Aw = p[3]*N
    τd = p[4]
    Rs = p[5]*N
    Cs = p[6]/N

    Z1b = RCS([Rct, Cdl, Aw, τd], frequencies)

    Z1s = RCO([Rs, Cs], frequencies)
    Zran = Z1b + Z1s
    Req = Zran
    for i in range(1, N):

        Req_inv = (1/(Req+Rpore))+1/Zran
        Req = 1/Req_inv

    Req = Req+Rpore

    I1 = np.zeros((len(frequencies), N), dtype=complex)
    for freq in range(0, len(frequencies)):
        b1 = np.ones(N)*Req[freq]

        A = np.identity(N)*Zran[freq]

        A1 = np.ones((N, N))*Rpore

        for i in range(0, N):

            A1[i, :] = A1[i, :]*(i+1)

            for j in range(0, i):

                A[i][j] = -(i-j)*Rpore

        A = A+A1

        b = b1

        I1[freq, :] = np.linalg.solve(A, b)

    return (I1)


@element(num_params=11, units=['Ohm', 'Ohm', 'F', 'Ohm', 's', 'Ohm', 'F', '',
                               '1/V', '', ''])
def mTiSn(p, f):
    """

    2nd-NLEIS: nonlinear current distribution of
    nonlinear discrete transmission line model
    built based on the Randles circuit
    with spherical diffusion from Ji et al. [1]

    Notes
    -----

    .. math::



    **Parameters:**

    .. math::
        p[0] = R_{pore}; \\;
        p[1] = R_{ct,bulk}; \\;
        p[2] = C_{dl,bulk}; \\;
        p[3] = A_{w,bulk}; \\;
        p[4] = τ_{bulk}; \\;
        p[5] = R_{ct,surface}; \\;


    .. math::

        p[6] = C_{dl,surface}; \\;
        p[7] = N (\\text{number of circuit element}); \\;
        p[8] = κ_{bulk}; \\;

    .. math::
        p[9] = ε_{bulk}; \\;
        p[10] = ε_{surface}; \\;



    """
    I1 = mTiS(p[0:8], f)  # calculate the current fraction (1st harmonic)

    N = int(p[7])

    frequencies = np.array(f)

    Rpore = p[0]/N
    Rct = p[1]*N
    Cdl = p[2]/N
    Aw = p[3]*N
    τd = p[4]
    Rs = p[5]*N
    Cs = p[6]/N
    κ = p[8]
    eb = p[9]
    es = p[10]

    Z1b = RCS([Rct, Cdl, Aw, τd], frequencies)
    Z1s = RCO([Rs, Cs], frequencies)
    Z2b = RCSn([Rct, Cdl, Aw, τd, κ, eb], frequencies)
    Z2s = RCOn([Rs, Cs, es], frequencies)
    Z1b2t = RCS([Rct, Cdl, Aw, τd], 2*frequencies)
    Z1s2t = RCO([Rs, Cs], 2*frequencies)

    Z1 = Z1b+Z1s
    Z2 = Z2b+Z2s
    Z12t = Z1b2t+Z1s2t

    if N == 1:
        return (Z2)

    if N == 2:
        sum1 = Z1**2/(2*Z1+Rpore)**2
        sum2 = (Z12t*Rpore+Rpore**2)/((2*Z12t+Rpore)*(2*Z1+Rpore))
        Z = (sum1+sum2)*Z2
        return (Z)

    I2 = np.zeros((len(frequencies), N), dtype=complex)

    for freq in range(0, len(frequencies)):
        Ii = I1[freq]

        A = np.arange(N-1, 0, -1)
        A1 = np.arange(N-1, 0, -1)

        for i in range(0, N-2):
            for j in range(0, N-1-i):
                A1[j] = A1[j]-1
            A = np.vstack((A, A1))
        A = A*Rpore
        A = np.append(A, np.zeros((N-1, 1)), axis=1)
        A = np.append(A, np.zeros((1, N)), axis=0)
        A2 = np.zeros((N-1, N))
        for i in range(0, N-1):
            A2[i, 0] += 1
            A2[i, N-1-i] -= 1
        A2 = np.vstack((A2, np.zeros(N)))
        A2 = A2*Z12t[freq]

        A3 = np.vstack((np.zeros((N-1, N)), np.ones(N)))

        Ax = A2+A+A3

        b = np.zeros((N, 1), dtype=complex)

        for i in range(0, N-1):
            b[i] = Ii[-1]**2-Ii[i]**2

        # reverse the order to display
        # the correct result from small to larger N
        I2[freq, :] = np.linalg.solve(Ax, -b*Z2[freq]).flatten()[::-1]

    return (I2)


@element(num_params=8, units=['Ohm', 'Ohm', 'F', 'Ohm', 's', 'Ohm', 'F', ''])
def TLMD(p, f):
    """

    EIS: general discrete transmission line model
    built based on the Randles circuit with planar diffusion from Ji et al. [1]

    Notes
    -----

    .. math::


    **Parameters:**

    .. math::

        p[0] = R_{pore}; \\;
        p[1] = R_{ct,bulk}; \\;
        p[2] = C_{dl,bulk}; \\;
        p[3] = A_{w,bulk}; \\;
        p[4] = τ_{bulk}; \\;
        p[5] = R_{ct,surface}; \\;

    .. math::

        p[6] = C_{dl,surface}; \\;
        p[7] = N (\\text{number of circuit element}); \\;


    [1] Y. Ji, D.T. Schwartz,
    Second-Harmonic Nonlinear Electrochemical Impedance Spectroscopy:
    I. Analytical theory and equivalent circuit representations
    for planar and porous electrodes.
    J. Electrochem. Soc. (2023). `doi: 10.1149/1945-7111/ad15ca
    <https://doi.org/10.1149/1945-7111/ad15ca>`_.

    """

    N = int(p[7])
    frequencies = np.array(f)

    Rpore = p[0]/N
    Rct = p[1]*N
    Cdl = p[2]/N
    Aw = p[3]*N
    τd = p[4]
    Rs = p[5]*N
    Cs = p[6]/N

    Z1b = RCD([Rct, Cdl, Aw, τd], frequencies)

    Z1s = RCO([Rs, Cs], frequencies)
    Zran = Z1b + Z1s
    Req = Zran
    for i in range(1, N):

        Req_inv = (1/(Req+Rpore))+1/Zran
        Req = 1/Req_inv
    return (Req)


@element(num_params=11, units=['Ohm', 'Ohm', 'F', 'Ohm', 's', 'Ohm', 'F', '',
                               '1/V', '', ''])
def TLMDn(p, f):
    """

    2nd-NLEIS:
    Second harmonic nonlinear discrete transmission line model
    built based on the Randles circuit
    with planar diffusion from Ji et al. [1]

    Notes
    -----

    .. math::




    **Parameters:**

    .. math::
        p[0] = R_{pore}; \\;
        p[1] = R_{ct,bulk}; \\;
        p[2] = C_{dl,bulk}; \\;
        p[3] = A_{w,bulk}; \\;
        p[4] = τ_{bulk}; \\;
        p[5] = R_{ct,surface}; \\;

    .. math::
        p[6] = C_{dl,surface}; \\;
        p[7] = N (\\text{number of circuit element})
        p[8] = κ_{bulk}; \\;

    .. math::
        p[9] = ε_{bulk}; \\;
        p[10] = ε_{surface}; \\;



    """

    I1 = mTiD(p[0:8], f)  # calculate the current fraction (1st harmonic)

    N = int(p[7])
    frequencies = np.array(f)

    Rpore = p[0]/N
    Rct = p[1]*N
    Cdl = p[2]/N
    Aw = p[3]*N
    τd = p[4]
    Rs = p[5]*N
    Cs = p[6]/N
    κ = p[8]
    eb = p[9]
    es = p[10]

    f = 96485.3321233100184/(8.31446261815324*298)  # unit in 1/V

    Z1b = RCD([Rct, Cdl, Aw, τd], frequencies)
    Z1s = RCO([Rs, Cs], frequencies)
    Z2b = RCDn([Rct, Cdl, Aw, τd, κ, eb], frequencies)
    Z2s = RCOn([Rs, Cs, es], frequencies)
    Z1b2t = RCD([Rct, Cdl, Aw, τd], 2*frequencies)
    Z1s2t = RCO([Rs, Cs], 2*frequencies)

    Z1 = Z1b+Z1s
    Z2 = Z2b+Z2s
    Z12t = Z1b2t+Z1s2t

    if N == 1:
        return (Z2)

    if N == 2:
        sum1 = Z1**2/(2*Z1+Rpore)**2
        sum2 = (Z12t*Rpore+Rpore**2)/((2*Z12t+Rpore)*(2*Z1+Rpore))
        Z = (sum1+sum2)*Z2
        return (Z)
    Z = np.zeros((len(frequencies)), dtype=complex)
    for freq in range(0, len(frequencies)):
        Ii = I1[freq]

        A = np.arange(N-1, 0, -1)
        A1 = np.arange(N-1, 0, -1)

        for i in range(0, N-2):
            for j in range(0, N-1-i):
                A1[j] = A1[j]-1
            A = np.vstack((A, A1))
        A = A*Rpore
        A = np.append(A, np.zeros((N-1, 1)), axis=1)
        A = np.append(A, np.zeros((1, N)), axis=0)
        A2 = np.zeros((N-1, N))
        for i in range(0, N-1):
            A2[i, 0] += 1
            A2[i, N-1-i] -= 1
        A2 = np.vstack((A2, np.zeros(N)))
        A2 = A2*Z12t[freq]

        A3 = np.vstack((np.zeros((N-1, N)), np.ones(N)))

        Ax = A2+A+A3

        b = np.zeros((N, 1), dtype=complex)

        for i in range(0, N-1):
            b[i] = Ii[-1]**2-Ii[i]**2

        I2 = np.linalg.solve(Ax, -b*Z2[freq])
        Z[freq] = Z2[freq]*Ii[0]**2+I2[-1]*Z12t[freq]
    return (Z)


@element(num_params=8, units=['Ohm', 'Ohm', 'F', 'Ohm', 's', 'Ohm', 'F', ''])
def mTiD(p, f):
    """

    EIS: current distribution of discrete transmission line model
    built based on the Randles circuit with planar diffusion from Ji et al. [1]

    Notes
    -----

    .. math::




    **Parameters:**

    .. math::
        p[0] = R_{pore}; \\;
        p[1] = R_{ct,bulk}; \\;
        p[2] = C_{dl,bulk}; \\;
        p[3] = A_{w,bulk}; \\;
        p[4] = τ_{bulk}; \\;
        p[5] = R_{ct,surface}; \\;

    .. math::
        p[6] = C_{dl,surface}; \\;
        p[7] = N (\\text{number of circuit element}); \\;


    [1] Y. Ji, D.T. Schwartz,
    Second-Harmonic Nonlinear Electrochemical Impedance Spectroscopy:
    I. Analytical theory and equivalent circuit representations
    for planar and porous electrodes.
    J. Electrochem. Soc. (2023). `doi: 10.1149/1945-7111/ad15ca
    <https://doi.org/10.1149/1945-7111/ad15ca>`_.

    """

    N = int(p[7])
    frequencies = np.array(f)

    Rpore = p[0]/N
    Rct = p[1]*N
    Cdl = p[2]/N
    Aw = p[3]*N
    τd = p[4]
    Rs = p[5]*N
    Cs = p[6]/N

    Z1b = RCD([Rct, Cdl, Aw, τd], frequencies)

    Z1s = RCO([Rs, Cs], frequencies)
    Zran = Z1b + Z1s
    Req = Zran
    for i in range(1, N):

        Req_inv = (1/(Req+Rpore))+1/Zran
        Req = 1/Req_inv

    Req = Req+Rpore

    I1 = np.zeros((len(frequencies), N), dtype=complex)
    for freq in range(0, len(frequencies)):
        b1 = np.ones(N)*Req[freq]

        A = np.identity(N)*Zran[freq]

        A1 = np.ones((N, N))*Rpore

        for i in range(0, N):

            A1[i, :] = A1[i, :]*(i+1)

            for j in range(0, i):

                A[i][j] = -(i-j)*Rpore

        A = A+A1

        b = b1

        I1[freq, :] = np.linalg.solve(A, b)
    return (I1)


@element(num_params=11, units=['Ohm', 'Ohm', 'F', 'Ohm', 's', 'Ohm', 'F', '',
                               '1/V', '', ''])
def mTiDn(p, f):
    """

    2nd-NLEIS: current distribution of
    Second harmonic nonlinear discrete transmission line model
    built based on the Randles circuit
    with planar diffusion from Ji et al. [1]

    Notes
    -----

    .. math::



    **Parameters:**

    .. math::

        p[0] = R_{pore}; \\;
        p[1] = R_{ct,bulk}; \\;
        p[2] = C_{dl,bulk}; \\;
        p[3] = A_{w,bulk}; \\;
        p[4] = τ_{bulk}; \\;
        p[5] = R_{ct,surface}; \\;


    .. math::

        p[6] = C_{dl,surface}; \\;
        p[7] = N (\\text{number of circuit element}); \\;
        p[8] = κ_{bulk}; \\;
        p[9] = ε_{bulk}; \\;
        p[10] = ε_{surface}; \\;



    """

    I1 = mTiD(p[0:8], f)  # calculate the current fraction (1st harmonic)

    N = int(p[7])
    frequencies = np.array(f)

    Rpore = p[0]/N
    Rct = p[1]*N
    Cdl = p[2]/N
    Aw = p[3]*N
    τd = p[4]
    Rs = p[5]*N
    Cs = p[6]/N
    κ = p[8]
    eb = p[9]
    es = p[10]

    f = 96485.3321233100184/(8.31446261815324*298)  # unit in 1/V

    Z1b = RCD([Rct, Cdl, Aw, τd], frequencies)
    Z1s = RCO([Rs, Cs], frequencies)
    Z2b = RCDn([Rct, Cdl, Aw, τd, κ, eb], frequencies)
    Z2s = RCOn([Rs, Cs, es], frequencies)
    Z1b2t = RCD([Rct, Cdl, Aw, τd], 2*frequencies)
    Z1s2t = RCO([Rs, Cs], 2*frequencies)

    Z1 = Z1b+Z1s
    Z2 = Z2b+Z2s
    Z12t = Z1b2t+Z1s2t

    if N == 1:
        return (Z2)

    if N == 2:
        sum1 = Z1**2/(2*Z1+Rpore)**2
        sum2 = (Z12t*Rpore+Rpore**2)/((2*Z12t+Rpore)*(2*Z1+Rpore))
        Z = (sum1+sum2)*Z2
        return (Z)

    I2 = np.zeros((len(frequencies), N), dtype=complex)

    for freq in range(0, len(frequencies)):
        Ii = I1[freq]

        A = np.arange(N-1, 0, -1)
        A1 = np.arange(N-1, 0, -1)

        for i in range(0, N-2):
            for j in range(0, N-1-i):
                A1[j] = A1[j]-1
            A = np.vstack((A, A1))
        A = A*Rpore
        A = np.append(A, np.zeros((N-1, 1)), axis=1)
        A = np.append(A, np.zeros((1, N)), axis=0)
        A2 = np.zeros((N-1, N))
        for i in range(0, N-1):
            A2[i, 0] += 1
            A2[i, N-1-i] -= 1
        A2 = np.vstack((A2, np.zeros(N)))
        A2 = A2*Z12t[freq]

        A3 = np.vstack((np.zeros((N-1, N)), np.ones(N)))

        Ax = A2+A+A3

        b = np.zeros((N, 1), dtype=complex)

        for i in range(0, N-1):
            b[i] = Ii[-1]**2-Ii[i]**2

        # reverse the order to display
        # the correct result from small to larger N
        I2[freq, :] = np.linalg.solve(Ax, -b*Z2[freq]).flatten()[::-1]

    return (Z)


def get_element_from_name(name):
    excluded_chars = '0123456789_'
    return ''.join(char for char in name if char not in excluded_chars)


def typeChecker(p, f, name, length):
    assert isinstance(p, list), \
        'in {}, input must be of type list'.format(name)
    for i in p:
        assert isinstance(i, (float, int, np.int32, np.float64)), \
            'in {}, value {} in {} is not a number'.format(name, i, p)
    for i in f:
        assert isinstance(i, (float, int, np.int32, np.float64)), \
            'in {}, value {} in {} is not a number'.format(name, i, f)
    assert len(p) == length, \
        'in {}, input list must be length {}'.format(name, length)
    return
