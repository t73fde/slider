FROM t73fde/slider-base
COPY setup.py setup.cfg README.rst MANIFEST.in /usr/src/slider/
COPY slider /usr/src/slider/slider/
WORKDIR /usr/src/slider
RUN ln /bin/python3 /bin/python && \
    python setup.py install
WORKDIR /
RUN rm -rf /usr/src/slider
VOLUME /home/slides
VOLUME /home/slider.bib
COPY docker/slider.ini /etc/slider

EXPOSE 29548
# USER nobody
CMD ["/usr/local/bin/slider", "-D", "-B", "-H", "0.0.0.0"]
