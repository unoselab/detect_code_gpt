def agc_mixed_005_01(url, brow_bin='mozilla', subj=None):
    """ Given a URL, try to pop it up in a browser on most platforms.
    brow_bin is only used on OS's where there is no "open" or "start" cmd.
    """

    if brow_bin is None:
        brow_bin ='mozilla'
    if subj is None:
        subj = 'Launching browser'
    if sys.platform == 'win32':
        os.startfile(url)
    elif sys.platform == 'darwin':
        subprocess.Popen(['open', url])
    elif sys.platform == 'linux2':
        subprocess.Popen(['xdg-open', url])
    else:
        try:
            subprocess.Popen([brow_bin, url])
        except OSError:
            print('Could not launch browser: %s' % brow_bin)
            print('Please visit %s in your browser.' % url) 

def agc_mixed_005_02(self, template):
        """Get the context for a template.

        If no matching value is found, an empty context is returned.
        Otherwise, this returns either the matching value if the value is
        dictionary-like or the dictionary returned by calling it with
        *template* if the value is a function.

        If several matching values are found, the resulting dictionaries will
        be merged before being returned if mergecontexts is True. Otherwise,
        only the first matching value is returned.

        :param template: the template to get the context for
        """
        context = {}
        for key, value in self.context.items():
            if key == template:
                if isinstance(value, dict):
                    context.update(value)
                elif callable(value):
                    context.update(value(template))
                else:
                    context.update(value)
        return context 

def hwc_mixed_005_03(self, profile):
        """
        Prompts the user to edit the given profile.

        :param      profile | <projexui.widgets.xviewwidget.XViewProfile>
        """
        mod = XViewProfileDialog.edit(self.window(), profile)
        if not mod:
            return False

        # update the action interface
        for act in self._profileGroup.actions():
            if act.profile() == profile:
                act.setProfile(profile)
                break

        # signal the change
        if not self.signalsBlocked():
            self.profileChanged.emit(profile)
            self.profilesChanged.emit()

        return True 

def hwc_mixed_005_04(self, roi_mask):
        """Removes voxels outside the given mask or ROI set."""

        # TODO ensure compatible with input image
        #   - must have < N dim and same size in moving dims.
        rows_to_delete = list() # to allow for additional masks to be applied in the future
        if isinstance(roi_mask,
                      np.ndarray):  # not (roi_mask is None or roi_mask=='auto'):
            self._set_roi_mask(roi_mask)

            rows_roi = np.where(self.roi_mask.flatten() == cfg.background_value)

            # TODO below would cause differences in size/shape across mask and carpet!
            self.carpet = np.delete(self.carpet, rows_roi, axis=0)

        else:
            self.roi_mask = np.ones(self.carpet.shape) 

def hwc_mixed_005_05(self, loop, user_data=None):
        """
        Update the graph and schedule the next update
        This is where the magic happens
        """
        self.view.update_displayed_information()

        # Save to CSV if configured
        if self.save_csv or self.csv_file is not None:
            output_to_csv(self.view.summaries, self.csv_file)

        # Set next update
        self.animate_alarm = loop.set_alarm_in(
            float(self.refresh_rate), self.animate_graph)

        if self.args.debug_run:
            # refresh rate is a string in float format
            self.debug_run_counter += int(float(self.refresh_rate))
            if self.debug_run_counter >= 8:
                self.exit_program() 

def agc_mixed_005_06(self, cfg, filename, print_ir=False, format='dot', options=None):
        """Save basic block graph into a file.
        """
        if format == 'dot':
            self.save_dot(cfg, filename, print_ir, options)
        elif format == 'pdf':
            self.save_pdf(cfg, filename, print_ir, options)
        elif format == 'png':
            self.save_png(cfg, filename, print_ir, options)
        elif format =='svg':
            self.save_svg(cfg, filename, print_ir, options)
        elif format == 'json':
            self.save_json(cfg, filename, print_ir, options)
        else:
            raise ValueError('Unknown format: %s' % format)
