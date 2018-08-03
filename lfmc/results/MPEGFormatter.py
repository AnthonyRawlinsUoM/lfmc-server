import matplotlib.pyplot as plt
import matplotlib.animation as animation

import logging

logging.basicConfig(filename='/var/log/lfmcserver.log', level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger(__name__)


class MPEGFormatter:

    @staticmethod
    async def format(data, variable):

        if data[variable].name is not None:
            video_name = "/tmp/temp%s.mp4" % data[variable].name
        else:
            video_name = "/tmp/temp.mp4"

        # Writer = animation.writers['ffmpeg']
        # writer = Writer(fps=15, metadata=dict(artist='Me'), bitrate=1800)

        frames = []
        fig = plt.figure(figsize=(16, 9), dpi=120)
        plt.ylabel('latitude')
        plt.xlabel('longitude')
        # plt.title(data.attrs["long_name"])  # TODO - not in all datasets!
        logger.debug("\n--> Building MP4")

        ts = len(data["time"])
        for t in range(0, ts):
            b = data.isel(time=t)
            im = b[variable]
            plt.text(3, 1, "%s" % b["time"].values)
            frame = plt.imshow(im, cmap='viridis_r', animated=True)
            # Push onto array of frames
            frames.append([frame])
            logger.debug("\n--> Generated frame %s of %s" % (t + 1, ts))

        vid = animation.ArtistAnimation(fig, frames, interval=50, blit=True, repeat_delay=1000)
        vid.save(video_name, writer='ffmpeg', codec='mpeg4')
        logger.debug("\n--> Successfully wrote temp MP4 file.")
        return video_name
