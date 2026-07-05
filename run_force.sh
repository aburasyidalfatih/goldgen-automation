#!/bin/bash
docker exec goldgen-bot bash -c "cp auto_poster.py force_poster.py && sed -i 's/if not self.should_post(fanspage):/if False:/g' force_poster.py && sed -i 's/poster = GoldGenAutoPoster()/poster = GoldGenAutoPoster(); poster.fanspage_delay_minutes = 0/g' force_poster.py && python force_poster.py"
