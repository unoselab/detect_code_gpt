def agc_mixed_005_01(lons, lats):
        """
        Compute the BoundingBox from a set of latitudes and longitudes

        :param lons: longitudes
        :param lats: latitudes
        :return: BoundingBox
        """
        if not lons or not lats:
            raise ValueError("Longitude and latitude sequences must not be empty")
        if len(lons) != len(lats):
            raise ValueError("Longitude and latitude sequences must have the same length")
        min_lon = min(lons)
        max_lon = max(lons)
        min_lat = min(lats)
        max_lat = max(lats)
        return BoundingBox(min_lon, min_lat, max_lon, max_lat) 

def agc_mixed_005_02(cls, session, **kwargs):
        """
        Get all local users.

        :param session: SQLAlchemy session
        :type session: :class:`sqlalchemy.Session`

        :return: local users
        :rtype: generator of :class:`pyshop.models.User`
        """
        query = session.query(cls)
        # Apply any additional filters passed via kwargs
        if kwargs:
            query = query.filter_by(**kwargs)
        # Assume a boolean column `is_local` indicates local users
        query = query.filter_by(is_local=True)
        # Use yield_per for memory‑efficient iteration
        query = query.yield_per(100)
        return (user for user in query) 

def agc_mixed_005_03(exctype, value, traceback):
    """
    This exception handler catches KeyboardInterrupt to cancel the Runner and
    also stops the Runner in case of an error.
    """
    runner = globals().get('runner')
    if runner is None:
        return
    if exctype is KeyboardInterrupt:
        try:
            runner.cancel()
        except Exception:
            pass
    else:
        try:
            runner.stop()
        except Exception:
            pass 

def hwc_mixed_005_04(self, base_dn, samaccountname, attributes=(), explicit_membership_only=False):
        """Produces a single, populated ADGroup object through the object factory.
        Does not populate attributes for the caller instance.

        sAMAccountName may not be present in group objects in modern AD schemas.
        Searching by common name and object class (group) may be an alternative
        approach if required in the future.

        :param str base_dn: The base DN to search within
        :param str samaccountname: The group's sAMAccountName
        :param list attributes: Object attributes to populate, defaults to all

        :return: A populated ADGroup object
        :rtype: ADGroup
        """

        groups = self.groups(base_dn, samaccountnames=[samaccountname], attributes=attributes,
                             explicit_membership_only=explicit_membership_only)

        try:
            # Usually we will find a match, but perhaps not always
            return groups[0]
        except IndexError:
            logging.info("%s - unable to retrieve object from AD by sAMAccountName", samaccountname) 

def hwc_mixed_005_05(self, U, mode):

        """
        Unfolded tensor times Khatri-Rao product for Kruskal tensors

        Parameters
        ----------
        X : tensor_mixin
            Tensor whose unfolding should be multiplied.
        U : list of array_like
            Matrices whose Khatri-Rao product should be multiplied.
        mode : int
            Mode in which X should be unfolded.

        See also
        --------
        sktensor.sptensor.uttkrp : Efficient computation of uttkrp for sparse tensors
        ttensor.uttkrp : Efficient computation of uttkrp for Tucker operators
        """
        N = self.ndim
        if mode == 1:
            R = U[1].shape[1]
        else:
            R = U[0].shape[1]
        W = np.tile(self.lmbda, 1, R)
        for i in range(mode) + range(mode + 1, N):
            W = W * dot(self.U[i].T, U[i])
        return dot(self.U[mode], W) 

def hwc_mixed_005_06(name, shape, trainable):
        """
        :param name: string
        :param shape: 4D array
        :return: tf variable
        """
        w = tf.get_variable(name=name, shape=shape, initializer=tf.contrib.layers.variance_scaling_initializer(),
                            trainable=trainable)
        weights_norm = tf.reduce_sum(tf.nn.l2_loss(w),
                                     name=name + '_norm')  # Should user want to optimize weight decay
        tf.add_to_collection('weight_losses', weights_norm)
        return w
