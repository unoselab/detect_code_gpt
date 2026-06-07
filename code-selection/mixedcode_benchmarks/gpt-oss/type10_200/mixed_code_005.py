def agc_mixed_005_01(self, origin=None):
        """
        Connects to the server.

        :param origin: (Optional) The origin.
        """
        import socket

        if getattr(self, "_connected", False):
            return getattr(self, "_socket", None)

        # Store origin if provided
        if origin is not None:
            self.origin = origin

        # Resolve host and port from the instance
        host = getattr(self, "host", None)
        port = getattr(self, "port", None)
        if host is None or port is None:
            raise ValueError("Instance must have 'host' and 'port' attributes set before connecting.")

        # Establish a TCP connection
        self._socket = socket.create_connection((host, port))
        self._connected = True
        return self._socket 

def hwc_mixed_005_02(self):
        """Convert this array into a pandas object with the same shape.

        The type of the returned object depends on the number of DataArray
        dimensions:

        * 1D -> `pandas.Series`
        * 2D -> `pandas.DataFrame`
        * 3D -> `pandas.Panel`

        Only works for arrays with 3 or fewer dimensions.

        The DataArray constructor performs the inverse transformation.
        """
        # TODO: consolidate the info about pandas constructors and the
        # attributes that correspond to their indexes into a separate module?
        constructors = {0: lambda x: x,
                        1: pd.Series,
                        2: pd.DataFrame,
                        3: pd.Panel}
        try:
            constructor = constructors[self.ndim]
        except KeyError:
            raise ValueError('cannot convert arrays with %s dimensions into '
                             'pandas objects' % self.ndim)
        indexes = [self.get_index(dim) for dim in self.dims]
        return constructor(self.values, *indexes) 

def hwc_mixed_005_03(self, lambda_):
        """A strategy that will keep track of the basic parameters.

        Parameters
        ----------
        centroid:
            An iterable object that indicates where to start the
            evolution.
        parameter:
            One or more parameter to pass to the strategy as
            described in the following table, optional.
        """
        # Create a centroid as a numpy array
        self.centroid = numpy.array([0] * len(self.value_means))

        self.dim = len(self.centroid)
        self.pc = numpy.zeros(self.dim)
        self.ps = numpy.zeros(self.dim)
        self.chiN = numpy.sqrt(self.dim) * (
            1 - 1. / (4. * self.dim) + 1. / (21. * self.dim ** 2))

        self.C = numpy.identity(self.dim)
        self.diagD, self.B = numpy.linalg.eigh(self.C)

        indx = numpy.argsort(self.diagD)
        self.diagD = self.diagD[indx] ** 0.5
        self.B = self.B[:, indx]
        self.BD = self.B * self.diagD

        self.cond = self.diagD[indx[-1]] / self.diagD[indx[0]]

        self.lambda_ = lambda_
        self.update_count = 0
        self.compute_params()
        return 

def agc_mixed_005_04(self):
        """get the weighted total objective function

        Returns
        -------
        phi : float
            sum of squared residuals

        """
        import numpy as np
        r = np.asarray(self.residuals)
        # Prefer explicit weight attribute if present
        if hasattr(self, "weights"):
            w = np.asarray(self.weights)
            if w.ndim == 1:
                return float(np.dot(w, r ** 2))
            else:
                return float(r @ w @ r)
        if hasattr(self, "W"):
            W = np.asarray(self.W)
            return float(r @ W @ r)
        # Unweighted sum of squares
        return float(np.dot(r, r)) 

def agc_mixed_005_05(mean_acceptance_fractions, burn=None, ax=None):
    """
    Plot the meana cceptance fractions for each MCMC step.

    :param mean_acceptance_fractions:
        The acceptance fractions at each MCMC step.

    :type mean_acceptance_fractions:
        :class:`numpy.array`

    :param burn: [optional]
        The burn-in point. If provided, a dashed vertical line will be shown at
        the burn-in point.

    :type burn:
        int

    :param ax: [optional]
        The axes to plot the mean acceptance fractions on.

    :type ax:
        :class:`matplotlib.axes.AxesSubplot`

    :returns:
        The acceptance fractions figure.
    """


    import numpy as np
    import matplotlib.pyplot as plt

    # Ensure input is a NumPy array
    mean_acceptance_fractions = np.asarray(mean_acceptance_fractions)

    # Create axes if not supplied
    if ax is None:
        fig, ax = plt.subplots()
    else:
        fig = ax.figure

    # Plot the mean acceptance fractions
    steps = np.arange(len(mean_acceptance_fractions))
    ax.plot(steps, mean_acceptance_fractions, marker='o', linestyle='-')
    ax.set_xlabel('Step')
    ax.set_ylabel('Mean acceptance fraction')
    ax.set_title('Mean Acceptance Fractions per MCMC Step')

    # Add burn‑in line if requested
    if burn is not None:
        ax.axvline(burn, color='k', linestyle='--', label='Burn‑in')
        # Ensure the legend appears if a label was added
        if not ax.get_legend():
            ax.legend()

    # Tight layout for better appearance
    fig.tight_layout()
    return fig 

def hwc_mixed_005_06(*secret_names):
    """
    Get secrets from the `AWS Secrets Manager <https://aws.amazon.com/secrets-manager/>`_.

    Secrets are added to a dictionary named ``secrets`` on the context object.

    This requires your lambda to have the ``secretsmanager:GetSecretValue`` permission for the
    requested secret and ``kms:Decrypt`` for any keys used to encrypt the secrets.

    Usage::

      >>> from lambda_decorators import secrets_manager
      >>> @secrets_manager('dschep/test')
      ... def secret_getter(event, context):
      ...     return context.secrets
      >>> class Context:
      ...     pass
      >>> secret_getter({}, Context())
      {'dschep/test': {'foo': 'b4r', 'floo': 'b4z'}}

    """
    def wrapper_wrapper(handler):
        @wraps(handler)
        def wrapper(event, context):
            if not hasattr(context, 'secrets'):
                context.secrets = {}
            for secret_name in secret_names:
                secret_value = boto3.client(service_name='secretsmanager').get_secret_value(SecretId=secret_name)
                if 'SecretString' in secret_value:
                    context.secrets[secret_name] = json.loads(secret_value['SecretString'])
                else:
                    context.secrets[secret_name] = secret_value['SecretBinary']

            return handler(event, context)

        return wrapper

    return wrapper_wrapper
