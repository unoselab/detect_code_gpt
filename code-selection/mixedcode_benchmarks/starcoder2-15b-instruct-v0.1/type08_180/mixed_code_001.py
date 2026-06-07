def agc_mixed_001_01(self, old_data):
        """
        Looks for changed relation fields between new and old data (before/after save).
        Creates back_link references for updated fields.

        Args:
            old_data: Object's data before save.
        """
        for field in self._meta.fields:
            if isinstance(field, models.ForeignKey):
                old_value = old_data.get(field.name)
                new_value = getattr(self, field.name)
                if old_value!= new_value:
                    if old_value:
                        old_value.back_links.remove(self)
                    if new_value:
                        new_value.back_links.add(self) 

def agc_mixed_001_02(self):
        """Convert observed data to xarray."""
        return xr.Dataset(
            data_vars={
                "temperature": (["time"], self.temperature),
                "humidity": (["time"], self.humidity),
                "pressure": (["time"], self.pressure),
            },
            coords={
                "time": self.time,
                "latitude": self.latitude,
                "longitude": self.longitude,
            },
        ) 

def hwc_mixed_001_03(self, state_size=None, start=(), dataset='', backward=False):
        """Generate a sequence.

        Parameters
        ----------
        state_size : `int`, optional
            State size (default: parser.state_sizes[0]).
        start : `str` or `iterable` of `str`, optional
            Initial state (default: ()).
        dataset : `str`, optional
            Dataset key prefix.
        backward : `bool`, optional
            Link direction.

        Returns
        -------
        `generator` of `str`
            State generator.
        """
        if state_size is None:
            try:
                state_size = next(iter(self.parser.state_sizes))
            except StopIteration:
                return
        #elif (self.parser is not None
        #      and state_size not in self.parser.state_sizes):
        #    raise ValueError('invalid state size: {0}: not in {1}'
        #                     .format(state_size, self.parser.state_sizes))
        dataset += state_size_dataset(state_size)
        return self.storage.generate(start, state_size, dataset, backward) 

def agc_mixed_001_04(self, first=0, last=None):
        """
        Returns the center of momentum for all particles in the simulation.

        Parameters
        ----------
        first: int, optional
            If ``first`` is specified, only calculate the center of momentum starting
            from index=``first``.
        last : int or None, optional
            If ``last`` is specified only calculate the center of momentum up to 
            (but excluding) index=``last``.  Same behavior as Python's range function.

        Examples
        --------
        >>> sim = rebound.Simulation()
        >>> sim.add(m=1, x=-20)
        >>> sim.add(m=1, x=-10)
        >>> sim.add(m=1, x=0)
        >>> sim.add(m=1, x=10)
        >>> sim.add(m=1, x=20)
        >>> com = sim.calculate_com()
        >>> com.x
        0.0 
        >>> com = sim.calculate_com(first=2,last=4) # Considers indices 2,3
        >>> com.x
        5.0

        """
        if last is None:
            last = len(self.particles)
        com = rebound.Particle()
        total_mass = 0
        for i in range(first, last):
            p = self.particles[i]
            total_mass += p.m
            com.x += p.x * p.m
            com.y += p.y * p.m
            com.z += p.z * p.m
        com.x /= total_mass
        com.y /= total_mass
        com.z /= total_mass
        return com 

def hwc_mixed_001_05(value, msg=None, except_=None, inc_zeros=True):
    """
    is defined, but null or empty like value
    """
    if hasattr(value, 'empty'):
        # dataframes must check for .empty
        # since they don't define truth value attr
        # take the negative, since below we're
        # checking for cases where value 'is_null'
        value = not bool(value.empty)
    elif inc_zeros and value in ZEROS:
        # also consider 0, 0.0, 0L as 'empty'
        # will check for the negative below
        value = True
    else:
        pass
    _is_null = is_null(value, except_=False)
    result = bool(_is_null or not value)
    if except_:
        return is_true(result, msg=msg, except_=except_)
    else:
        return bool(result) 

def hwc_mixed_001_06(self):
        """
        Array for the optimizer to work on.
        This array always lives in the space for the optimizer.
        Thus, it is untransformed, going from Transformations.

        Setting this array, will make sure the transformed parameters for this model
        will be set accordingly. It has to be set with an array, retrieved from
        this method, as e.g. fixing will resize the array.

        The optimizer should only interfere with this array, such that transformations
        are secured.
        """
        if self.__dict__.get('_optimizer_copy_', None) is None or self.size != self._optimizer_copy_.size:
            self._optimizer_copy_ = np.empty(self.size)

        if not self._optimizer_copy_transformed:
            self._optimizer_copy_.flat = self.param_array.flat
            #py3 fix
            #[np.put(self._optimizer_copy_, ind, c.finv(self.param_array[ind])) for c, ind in self.constraints.iteritems() if c != __fixed__]
            [np.put(self._optimizer_copy_, ind, c.finv(self.param_array[ind])) for c, ind in self.constraints.items() if c != __fixed__]
            self._optimizer_copy_transformed = True

        if self._has_fixes():# or self._has_ties()):
            self._ensure_fixes()
            return self._optimizer_copy_[self._fixes_]
        return self._optimizer_copy_
