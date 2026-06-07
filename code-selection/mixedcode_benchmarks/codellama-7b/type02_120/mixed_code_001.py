def hwc_mixed_001_01(self):
        """Get unordered list of scheduling block ids"""

        # Initialise empty list
        scheduling_block_ids = []

        # Pattern used to search scheduling block ids
        pattern = 'scheduling_block:*'
        block_ids = self._db.get_ids(pattern)

        for block_id in block_ids:
            if 'processing_block' not in block_id:
                id_split = block_id.split(':')[-1]
                scheduling_block_ids.append(id_split)
        return sorted(scheduling_block_ids) 

def hwc_mixed_001_02(self, unique_name_file):
        """
        logs the agent details to logfile
        unique_name_file (list_agents.txtlist_agents_names.txt) = list of all instances of all agents
        """
        agt_list = os.path.join(root_fldr, 'data', unique_name_file)
        if os.path.exists(agt_list):
            agents_logged = open(agt_list, 'r').read()
        else:
            agents_logged = ''
        print('agents_logged = ', agents_logged)
        if self._get_instance() not in agents_logged:
            with open(agt_list, 'a') as f:
                f.write(self._get_instance() + '\n') 

def agc_mixed_001_03(self, dt=None):
        """Simulate the model for a given time interval.

        Parameters
        ----------
        dt : Optional[float]
            The time step to simulate, if None, the default built-in time step
            is used.
        """
        # EMELI passes dt = -1 so we need to handle that here
        if dt is None:
            dt = self.dt
        self.t += dt
        self.t_now = self.t
        self.t_prev = self.t - dt
        self.t_next = self.t + dt

        # Update the state of the model
        self.update_state(dt)

        # Update the model
        self.update_model(dt) 

async def agc_mixed_001_04(self):
        """lets you type a page number to go to"""
        try:
            page_number = int(input("Enter the page number: "))
            if page_number > self.number_of_pages():
                print("That page doesn't exist")
            else:
                self.go_to_page(page_number)
        except ValueError:
            print("That's not a number") 

def hwc_mixed_001_05(self, dt):
        """
        Given a dt, find that day's close and period start (close - offset).
        """
        period_end = self.cal.open_and_close_for_session(
            self.cal.minute_to_session_label(dt),
        )[1]

        # Align the market close time here with the execution time used by the
        # simulation clock. This ensures that scheduled functions trigger at
        # the correct times.
        self._period_end = self.cal.execution_time_from_close(period_end)

        self._period_start = self._period_end - self.offset
        self._period_close = self._period_end 

def agc_mixed_001_06(self):
        """ just loop and write responses """

        while True:
            try:
                self.write_response()
            except Exception as e:
                self.logger.error(e)
                self.logger.error(traceback.format_exc())
                self.logger.error("Exiting...")
                break
