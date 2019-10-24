import queue

import pyqtgraph as pg
from pyqtgraph.Qt import QtGui, QtCore
import numpy as np

from app.lib.dsp import ExpFilter
from app.lib.pubsub import subscribe
from app import Task


class GUI(Task):
    def start(self):
        super().start()
        self.fft_plot_filter = ExpFilter(np.tile(1e-1, self.config['N_FFT_BINS']),
                         alpha_decay=0.5, alpha_rise=0.99)
        self.led_plots = {}
        self.make_gui()

        subscribe('audio', self.handle)

    def make_gui(self):
        # Create GUI window
        app = QtGui.QApplication([])
        view = pg.GraphicsView()
        layout = pg.GraphicsLayout(border=(100,100,100))
        view.setCentralItem(layout)
        view.show()
        view.setWindowTitle('Visualization')
        view.resize(800,600)
        # Mel filterbank plot
        fft_plot = layout.addPlot(title='Filterbank Output', colspan=3)
        fft_plot.setRange(yRange=[-0.1, 1.2])
        fft_plot.disableAutoRange(axis=pg.ViewBox.YAxis)
        x_data = np.array(range(1, self.config['N_FFT_BINS'] + 1))
        mel_curve = pg.PlotCurveItem()
        mel_curve.setData(x=x_data, y=x_data*0)
        fft_plot.addItem(mel_curve)

        def add_led_plot(o):
            # Visualization plot
            layout.nextRow()
            led_plot = layout.addPlot(title='LED: ' + o['NAME'], colspan=3)
            led_plot.setRange(yRange=[-5, 260])
            led_plot.disableAutoRange(axis=pg.ViewBox.YAxis)
            # Pen for each of the color channel curves
            r_pen = pg.mkPen((255, 30, 30, 200), width=4)
            g_pen = pg.mkPen((30, 255, 30, 200), width=4)
            b_pen = pg.mkPen((30, 30, 255, 200), width=4)
            # Color channel curves
            r_curve = pg.PlotCurveItem(pen=r_pen)
            g_curve = pg.PlotCurveItem(pen=g_pen)
            b_curve = pg.PlotCurveItem(pen=b_pen)
            # Define x data
            x_data = np.array(range(1, o['N_PIXELS'] + 1))
            r_curve.setData(x=x_data, y=x_data*0)
            g_curve.setData(x=x_data, y=x_data*0)
            b_curve.setData(x=x_data, y=x_data*0)
            # Add curves to plot
            led_plot.addItem(r_curve)
            led_plot.addItem(g_curve)
            led_plot.addItem(b_curve)

            subscribe('led_data', self.handle_led_data)

            self.led_plots[o['NAME']] = (led_plot, r_curve, g_curve, b_curve)

        for o in self.config.get('OUTPUTS') or []:
            # TODO: better way to figure this out
            if o.get('DEVICE', '').endswith('Strip'):
                add_led_plot(o)

        # Frequency range label
        freq_label = pg.LabelItem('')
        # Frequency slider
        def freq_slider_change(tick):
            minf = freq_slider.tickValue(0)**2.0 * (self.config['MIC_RATE'] / 2.0)
            maxf = freq_slider.tickValue(1)**2.0 * (self.config['MIC_RATE'] / 2.0)
            t = 'Frequency range: {:.0f} - {:.0f} Hz'.format(minf, maxf)
            freq_label.setText(t)
            self.config['MIN_FREQUENCY'] = minf
            self.config['MAX_FREQUENCY'] = maxf
            return
            dsp.create_mel_bank()
        freq_slider = pg.TickSliderItem(orientation='bottom', allowAdd=False)
        freq_slider.addTick((self.config['MIN_FREQUENCY'] / (self.config['MIC_RATE'] / 2.0))**0.5)
        freq_slider.addTick((self.config['MAX_FREQUENCY'] / (self.config['MIC_RATE'] / 2.0))**0.5)
        freq_slider.tickMoveFinished = freq_slider_change
        freq_label.setText('Frequency range: {} - {} Hz'.format(
            self.config['MIN_FREQUENCY'],
            self.config['MAX_FREQUENCY']))
        # # Effect selection
        # active_color = '#16dbeb'
        # inactive_color = '#FFFFFF'
        # def energy_click(x):
        #     global visualization_effect
        #     visualization_effect = visualize_energy
        #     energy_label.setText('Energy', color=active_color)
        #     scroll_label.setText('Scroll', color=inactive_color)
        #     spectrum_label.setText('Spectrum', color=inactive_color)
        # def scroll_click(x):
        #     global visualization_effect
        #     visualization_effect = visualize_scroll
        #     energy_label.setText('Energy', color=inactive_color)
        #     scroll_label.setText('Scroll', color=active_color)
        #     spectrum_label.setText('Spectrum', color=inactive_color)
        # def spectrum_click(x):
        #     global visualization_effect
        #     visualization_effect = visualize_spectrum
        #     energy_label.setText('Energy', color=inactive_color)
        #     scroll_label.setText('Scroll', color=inactive_color)
        #     spectrum_label.setText('Spectrum', color=active_color)
        # # Create effect "buttons" (labels with click event)
        # energy_label = pg.LabelItem('Energy')
        # scroll_label = pg.LabelItem('Scroll')
        # spectrum_label = pg.LabelItem('Spectrum')
        # energy_label.mousePressEvent = energy_click
        # scroll_label.mousePressEvent = scroll_click
        # spectrum_label.mousePressEvent = spectrum_click
        # energy_click(0)
        # Layout
        layout.nextRow()
        layout.addItem(freq_label, colspan=3)
        layout.nextRow()
        layout.addItem(freq_slider, colspan=3)
        layout.nextRow()
        # layout.addItem(energy_label)
        # layout.addItem(scroll_label)
        # layout.addItem(spectrum_label)

        self.app = app
        self.view = view
        self.layout = layout
        self.mel_curve = mel_curve

    def handle(self, mel):
        # Plot filterbank output
        x = np.linspace(self.config['MIN_FREQUENCY'], self.config['MAX_FREQUENCY'], len(mel))
        self.mel_curve.setData(x=x, y=self.fft_plot_filter.update(mel))

    def handle_led_data(self, data):
        # Plot the color channels
        if data['name'] not in self.led_plots:
            return
        _, r_curve, g_curve, b_curve = self.led_plots[data['name']]
        r_curve.setData(y=data['pixels'][0])
        g_curve.setData(y=data['pixels'][1])
        b_curve.setData(y=data['pixels'][2])

    def run(self):
        self.app.processEvents()
