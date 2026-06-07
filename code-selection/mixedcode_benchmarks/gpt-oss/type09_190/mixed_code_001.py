def hwc_mixed_001_01(left, right, key_left, key_right,
                cols_right=None):
    """Perform a join of two tables.

    Parameters
    ----------
    left : `~astropy.Table`
        Left table for join.

    right : `~astropy.Table`
        Right table for join.

    key_left : str
        Key used to match elements from ``left`` table.

    key_right : str
        Key used to match elements from ``right`` table.

    cols_right : list    
        Subset of columns from ``right`` table that will be appended
        to joined table.

    """
    right = right.copy()

    if cols_right is None:
        cols_right = right.colnames
    else:
        cols_right = [c for c in cols_right if c in right.colnames]

    if key_left != key_right:
        right[key_right].name = key_left

    if key_left not in cols_right:
        cols_right += [key_left]

    out = join(left, right[cols_right], keys=key_left,
               join_type='left')

    for col in out.colnames:
        if out[col].dtype.kind in ['S', 'U']:
            out[col].fill_value = ''
        elif out[col].dtype.kind in ['i']:
            out[col].fill_value = 0
        else:
            out[col].fill_value = np.nan

    return out.filled() 

def agc_mixed_001_02(interface='Local Area Connection'):
    """
    Get the type of DNS configuration (dhcp / static)

    CLI Example:

    .. code-block:: bash

        salt '*' win_dns_client.get_dns_config 'Local Area Connection'
    """
    # remove any escape characters
    import subprocess
    try:
        output = subprocess.check_output(
            ["netsh", "interface", "ip", "show", "dns", f'name="{interface}"'],
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

    for line in output.splitlines():
        line = line.strip().lower()
        if "dhcp" in line and "configured through dhcp" in line:
            return "dhcp"
        if "statically configured dns servers" in line:
            return "static"
    return None 

def agc_mixed_001_03(self):
        """Split the return objects by year and iterate"""
        from itertools import groupby

        # Collect items from the instance (assumes it is iterable)
        items = list(self)

        # Helper to extract year from an item
        def _year(item):
            # Try attribute 'date' with a 'year' attribute
            if hasattr(item, "date"):
                try:
                    return item.date.year
                except Exception:
                    pass
            # Direct ' 

def agc_mixed_001_04(self, index):
        """Set flags"""
        if not isinstance(index, int):
            raise TypeError(f"index must be int, got {type(index).__name__}")
        # Bitmask style flag storage
        if hasattr(self, "flags") and isinstance(self.flags, int):
            self.flags |= 1 << index
            return self.flags
        # List style flag storage
        if hasattr(self, "_flags"):
            if isinstance(self._flags, list):
                if index >= len(self._flags):
                    self._flags.extend([False] * (index - len(self._flags) + 1))
                self._flags[index] = True 

def hwc_mixed_001_05(query, db, type, out, threads = '4', evalue = '100', alignment = 'local'):
    """
    run usearch
    """
    if os.path.exists(out) is False:
        print('# ... running usearch with %s as query and %s as database' % (query, db))
        if type[1] == 'nucl':
            threads = ''
        else:
            threads = '-threads %s' % (threads)
        os.system('usearch \
                -query %s -%s %s -blast6out %s \
                -evalue %s %s -%s >> log.txt' \
                % (query, type[0], db, out, evalue, threads, alignment))
    else:
        print('# ... usearch output found for %s as query and %s as database' % (query, db)) 

def hwc_mixed_001_06(self,EndOfPrdvP,aNrmNow):
        """
        Find endogenous interpolation points for each asset point and each
        discrete preference shock.

        Parameters
        ----------
        EndOfPrdvP : np.array
            Array of end-of-period marginal values.
        aNrmNow : np.array
            Array of end-of-period asset values that yield the marginal values
            in EndOfPrdvP.

        Returns
        -------
        c_for_interpolation : np.array
            Consumption points for interpolation.
        m_for_interpolation : np.array
            Corresponding market resource points for interpolation.
        """
        c_base       = self.uPinv(EndOfPrdvP)
        PrefShkCount = self.PrefShkVals.size
        PrefShk_temp = np.tile(np.reshape(self.PrefShkVals**(1.0/self.CRRA),(PrefShkCount,1)),
                               (1,c_base.size))
        self.cNrmNow = np.tile(c_base,(PrefShkCount,1))*PrefShk_temp
        self.mNrmNow = self.cNrmNow + np.tile(aNrmNow,(PrefShkCount,1))

        # Add the bottom point to the c and m arrays
        m_for_interpolation = np.concatenate((self.BoroCnstNat*np.ones((PrefShkCount,1)),
                                              self.mNrmNow),axis=1)
        c_for_interpolation = np.concatenate((np.zeros((PrefShkCount,1)),self.cNrmNow),axis=1)
        return c_for_interpolation,m_for_interpolation
