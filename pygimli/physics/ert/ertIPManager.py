"""ERT manager (derived) with FD or TD IP inversion."""
import pygimli as pg
from .ertManager import ERTManager
from .ipModelling import DCIPMModelling


class ERTIPManager(ERTManager):
    """Method manager for ERT including induced polarization (IP).
    
    This class should be use for any single IP data, which can
    be a single-frequency frequency-domain (FD) amplitude and
    phase, or a time-domain (TD) IP chargeability (one gate or an
    integral value).
    """

    def __init__(self, *args, **kwargs):
        """Initialize DC part of it (parent class).
        
        Parameters
        ----------
        fd : bool
            Frequency-domain, otherwise time-domain
        """
        self.isfd = kwargs.pop("fd", False)
        super().__init__(*args, **kwargs)

    def invertTDIP(self, ipdata=None, **kwargs):
        """IP inversion in time domain."""
        ipdata = ipdata or self.data["ip"]
        if max(ipdata) > 1:  # mV/V
            ipdata /= 1000
        mesh0 = pg.Mesh(self.paraDomain)
        mesh0.setCellMarkers(mesh0.cellCount())
        fopIP = DCIPMModelling(self.fop, mesh0, self.model, response=self.inv.response)
        fopIP.createRefinedForwardMesh(True)
        invIP = pg.Inversion(fop=fopIP, verbose=True)
        invIP.modelTrans = pg.trans.TransLogLU(0.0, 1.0)
        errorIP = pg.Vector(self.data.size(), 0.03) + 0.001 / ipdata  # absolute ma 1mV/V plus 3%
        kwargs.setdefault("lam", 100)
        kwargs.setdefault("startModel", pg.median(ipdata))
        kwargs.setdefault("verbose", True)
        self.modelIP = invIP.run(ipdata, errorIP, **kwargs)

    def invertFDIP(self, **kwargs):
        """IP inversion in frequency domain."""
        self.modelIP = None  # naive IP inversion

    def showIPModel(self, **kwargs):
        """"Show IP model."""
        kwargs.setdefault("logSpace", False)
        if self.isfd:
            kwargs.setdefault("label", r"$\phi$ (mrad)")
            kwargs.setdefault("cMap", "viridis")
        else:
            kwargs.setdefault("label", r"$m$ (mV/V)")
            kwargs.setdefault("cMap", "magma_r")

        self.showModel(self.modelIP*1000, **kwargs)

    def showResults(self, reskw={}, ipkw={}, **kwargs):
        """Show DC and IP results.
        
        Parameters
        ----------
        reskw : dict
            keyword arguments for showing resistivity image
        ipkw : dict
            keyword arguments for showing IP image
        **kwargs : dict
            keyword arguments for showing resistivity image
        """
        _, ax = pg.plt.subplots(nrows=2, sharex=True)
        kwargs.setdefault("orientation", "vertical")
        reskw.setdefault("ax", ax[0])
        super().showResult(**reskw, **kwargs)
        ipkw.setdefault("ax", ax[1])
        ipkw.setdefault("logScale", False)
        ipkw.setdefault("cMin", 0)
        self.showIPModel(**ipkw, **kwargs)

    def invert(self, *args, **kwargs):
        """Carry out DC and IP inversion."""
        super().invert(*args, **kwargs)  # DC first (not needed for FD)
        if self.isfd:
            self.invertFDIP()
        else:
            self.invertTDIP()

    def simulate(self, *args, **kwargs):
        """."""
        pass