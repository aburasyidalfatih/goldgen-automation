from auto_poster import GoldGenAutoPoster

class ForcePoster(GoldGenAutoPoster):
    def should_post(self, fanspage):
        return True

if __name__ == '__main__':
    p = ForcePoster()
    p.fanspage_delay_minutes = 0
    p.run()
