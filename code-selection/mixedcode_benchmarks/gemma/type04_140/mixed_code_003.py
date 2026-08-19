def hwc_mixed_003_01(self, X):
        """
        Calculate the average spread for each node.

        The average spread is a measure of how far each neuron is from the
        data points which cluster to it.

        Parameters
        ----------
        X : numpy array
            The input data.

        Returns
        -------
        spread : numpy array
            The average distance from each neuron to each data point.

        """
        distance, _ = self.distance_function(X, self.weights)
        dists_per_neuron = defaultdict(list)
        for x, y in zip(np.argmin(distance, 1), distance):
            dists_per_neuron[x].append(y[x])

        out = np.zeros(self.num_neurons)
        average_spread = {k: np.mean(v)
                          for k, v in dists_per_neuron.items()}

        for x, y in average_spread.items():
            out[x] = y
        return out 

def hwc_mixed_003_02(self, rgb):
        """
        Determine the liminanace of an RGB colour
        """
        a = []
        for v in rgb:
            v = v / float(255)
            if v < 0.03928:
                result = v / 12.92
            else:
                result = math.pow(((v + 0.055) / 1.055), 2.4)

            a.append(result)
        return a[0] * 0.2126 + a[1] * 0.7152 + a[2] * 0.0722 

def hwc_mixed_003_03(self, is_dhcp, ip='', gate='', mask='',
                                dns1='', dns2='', callback=None):
        """
        isDHCP: 0(False), 1(True)
        System will reboot automatically to take effect after call this CGI command.
        """
        params = {'isDHCP': is_dhcp,
                  'ip': ip,
                  'gate': gate,
                  'mask': mask,
                  'dns1': dns1,
                  'dns2': dns2,
                 }

        return self.execute_command('setIpInfo', params, callback=callback) 

def agc_mixed_003_04(self):
        """Extract and return Youtube video id"""
        import re
        url = self.url if hasattr(self, 'url') else ""
        patterns = [
            r'(?:v=|\/embed\/|\/youtu\.be\/|\/v\/)([a-zA-Z0-9_-]{11})',
            r'shorts\/([a-zA-Z0-9_-]{11})'
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None 

def agc_mixed_003_05(self, id, filename, file, content_type, include_online=False):
        """Upload an attachment to the Xero object (from file object)."""
        url = f"{self.base_url}/Attachments/{id}"
        headers = {
            "Content-Type": content_type,
            "Accept": "application/json",
            "Xero-tenant-id": self.tenant_id
        }
        params = {"filename": filename}
        if include_online:
            params["online"] = "true"

        response = self.session.put(url, data=file, headers=headers, params=params)
        response.raise_for_status()
        return response.json() 

def agc_mixed_003_06(self):
        """Extract sample_stats from posterior."""
        import xarray as xr
        import numpy as np

        stats = self.posterior.sample_stats
        if stats is None:
            return None

        # Assuming stats is a dictionary or object with data and coordinates
        # Adjust based on the specific structure of sample_stats
        data = np.array(stats.get('data', []))
        coords = stats.get('coords', {})
        dims = stats.get('dims', [])

        return xr.DataArray(data, coords=coords, dims=dims, name='sample_stats')
