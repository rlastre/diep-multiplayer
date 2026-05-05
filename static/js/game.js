class PlayScene extends Phaser.Scene {

  constructor() {
    super('PlayScene');
    this.otherPlayers = {};
    this.itemSprites = {};
    this.myId = null;
    this.myColor = '#4488cc';
    this.myHp = 100;
    this.alive = true;
  }

  preload() {
    const bl = this.make.graphics({ add: false });
    bl.fillStyle(0xffcc00, 1);
    bl.fillCircle(4, 4, 4);
    bl.generateTexture('bullet', 8, 8);

    const item = this.make.graphics({ add: false });
    item.fillStyle(0x111111, 1);
    item.fillRect(0, 0, 20, 20);
    item.lineStyle(2, 0x444444, 1);
    item.strokeRect(0, 0, 20, 20);
    item.generateTexture('powerup', 20, 20);
  }

  create() {
    this.cameras.main.setBackgroundColor('#e8e4d8');

    const grid = this.add.graphics();
    grid.lineStyle(0.5, 0x000000, 0.07);
    for (let x = 0; x <= 800; x += 40) grid.lineBetween(x, 0, x, 600);
    for (let y = 0; y <= 600; y += 40) grid.lineBetween(0, y, 800, y);

    this.bullets = this.physics.add.group();
    this.hpGraphics = this.add.graphics().setDepth(50);

    this.keys = this.input.keyboard.addKeys({
      w: Phaser.Input.Keyboard.KeyCodes.W,
      a: Phaser.Input.Keyboard.KeyCodes.A,
      s: Phaser.Input.Keyboard.KeyCodes.S,
      d: Phaser.Input.Keyboard.KeyCodes.D,
    });
    this.lastShot = 0;

    this.statusText = this.add.text(14, 14, 'Connecting...', {
      fontFamily: 'Courier New', fontSize: '14px', color: '#333',
    });
    this.add.text(14, 570, 'WASD move · Mouse aim · Click shoot', {
      fontFamily: 'Courier New', fontSize: '13px', color: '#888',
    });
    this.deathText = this.add.text(400, 300, '', {
      fontFamily: 'Courier New', fontSize: '22px', color: '#cc0000',
      stroke: '#000', strokeThickness: 3,
    }).setOrigin(0.5).setDepth(200);

    this.socket = io({ reconnectionAttempts: 5 });

    this.socket.on('init', (data) => {
      this.myId = data.id;
      const me = data.players[this.myId];
      this.myColor = me.color;
      this.myHp = me.hp;
      this.alive = me.alive;

      this.clearAllRemotePlayers();
      this.clearAllItems();

      if (!this.tank) {
        this.createLocalTank(me.x, me.y, me.color);
      } else {
        this.tank.setPosition(me.x, me.y);
        this.tank.setVisible(true);
        this.barrel.setVisible(true);
      }

      for (const [pid, pdata] of Object.entries(data.players)) {
        if (pid !== this.myId) this.addRemotePlayer(pid, pdata);
      }
      for (const [iid, idata] of Object.entries(data.items)) {
        this.addItem(iid, idata);
      }
      this.updateStatus();
    });

    this.socket.on('player_joined', (data) => {
      if (!this.otherPlayers[data.id]) this.addRemotePlayer(data.id, data.data);
      this.updateStatus();
    });

    this.socket.on('player_left', (data) => {
      this.removeRemotePlayer(data.id);
      this.updateStatus();
    });

    this.socket.on('player_moved', (data) => {
      const remote = this.otherPlayers[data.id];
      if (!remote) return;
      remote.targetX = data.data.x;
      remote.targetY = data.data.y;
      remote.targetAngle = data.data.angle;
    });

    this.socket.on('player_shot', (data) => {
      this.spawnBullet(data.data.x, data.data.y, data.data.angle, data.id);
    });

    this.socket.on('player_damaged', (data) => {
      if (data.id === this.myId) {
        this.myHp = data.hp;
      } else if (this.otherPlayers[data.id]) {
        this.otherPlayers[data.id].hp = data.hp;
      }
    });

    this.socket.on('player_died', (data) => {
      if (data.id === this.myId) {
        this.alive = false;
        this.myHp = 0;
        this.tank.setVisible(false);
        this.barrel.setVisible(false);
        if (this.myNameTag) this.myNameTag.setVisible(false);
        this.deathText.setText('Killed by ' + data.killer_name + ' — respawning...');
      } else if (this.otherPlayers[data.id]) {
        this.otherPlayers[data.id].tank.setVisible(false);
        this.otherPlayers[data.id].barrel.setVisible(false);
        if (this.otherPlayers[data.id].nameTag) this.otherPlayers[data.id].nameTag.setVisible(false);
        this.otherPlayers[data.id].alive = false;
      }
    });

    this.socket.on('player_respawned', (data) => {
      if (data.id === this.myId) {
        this.alive = true;
        this.myHp = data.data.hp;
        this.tank.setPosition(data.data.x, data.data.y);
        this.tank.setScale(data.data.scale || 1);
        this.barrel.setScale(data.data.scale || 1);
        this.tank.setVisible(true);
        this.barrel.setVisible(true);
        if (this.myNameTag) this.myNameTag.setVisible(true);
        this.tank.setVelocity(0, 0);
        this.deathText.setText('');
      } else if (this.otherPlayers[data.id]) {
        const r = this.otherPlayers[data.id];
        r.tank.setPosition(data.data.x, data.data.y);
        r.targetX = data.data.x;
        r.targetY = data.data.y;
        r.tank.setScale(data.data.scale || 1);
        r.barrel.setScale(data.data.scale || 1);
        r.tank.setVisible(true);
        r.barrel.setVisible(true);
        if (r.nameTag) r.nameTag.setVisible(true);
        r.hp = data.data.hp;
        r.alive = true;
      }
    });

    this.socket.on('item_picked', (data) => {
      this.removeItem(data.item_id);
      if (data.player_id === this.myId) {
        this.tank.setScale(3);
        this.barrel.setScale(3);
      } else if (this.otherPlayers[data.player_id]) {
        this.otherPlayers[data.player_id].tank.setScale(3);
        this.otherPlayers[data.player_id].barrel.setScale(3);
      }
    });

    this.socket.on('item_spawned', (data) => {
      this.addItem(data.item_id, data.data);
    });
  }

  // Items
  addItem(id, data) {
    if (this.itemSprites[id]) return;
    const sprite = this.physics.add.image(data.x, data.y, 'powerup');
    sprite.setImmovable(true);
    sprite.body.setAllowGravity(false);
    sprite.setDepth(1);
    this.itemSprites[id] = sprite;
  }
  removeItem(id) {
    if (this.itemSprites[id]) { this.itemSprites[id].destroy(); delete this.itemSprites[id]; }
  }
  clearAllItems() {
    for (const id of Object.keys(this.itemSprites)) this.removeItem(id);
  }
  checkItemPickup() {
    if (!this.tank || !this.alive) return;
    for (const [id, sprite] of Object.entries(this.itemSprites)) {
      if (!sprite.active) continue;
      const dist = Phaser.Math.Distance.Between(this.tank.x, this.tank.y, sprite.x, sprite.y);
      if (dist < 30) this.socket.emit('pickup', { item_id: id });
    }
  }

  // Tanks
  createLocalTank(x, y, color) {
    const hexColor = parseInt(color.replace('#', ''), 16);
    const darkerHex = Phaser.Display.Color.ValueToColor(hexColor).darken(20).color;

    const tg = this.make.graphics({ add: false });
    tg.fillStyle(hexColor, 1);
    tg.fillRect(0, 0, 32, 32);
    tg.lineStyle(2, darkerHex, 1);
    tg.strokeRect(0, 0, 32, 32);
    tg.generateTexture('tank_local', 32, 32);

    const bg = this.make.graphics({ add: false });
    bg.fillStyle(0x777777, 1);
    bg.fillRect(0, 0, 28, 8);
    bg.lineStyle(1, 0x555555, 1);
    bg.strokeRect(0, 0, 28, 8);
    bg.generateTexture('barrel_local', 28, 8);

    this.tank = this.physics.add.image(x, y, 'tank_local');
    this.tank.setCollideWorldBounds(true);
    this.tank.setDrag(400);
    this.tank.setMaxVelocity(180);
    this.tank.setDepth(1);

    this.barrel = this.add.image(x, y, 'barrel_local');
    this.barrel.setOrigin(0, 0.5);
    this.barrel.setDepth(2);

    this.myNameTag = this.add.text(x, y - 36, window.PLAYER_NAME || 'You', {
      fontFamily: 'Courier New', fontSize: '11px', color: '#333',
    }).setOrigin(0.5).setDepth(51);
  }

  addRemotePlayer(pid, data) {
    const hexColor = parseInt(data.color.replace('#', ''), 16);
    const darkerHex = Phaser.Display.Color.ValueToColor(hexColor).darken(20).color;
    const tKey = 'tank_' + pid;
    const bKey = 'barrel_' + pid;

    const tg = this.make.graphics({ add: false });
    tg.fillStyle(hexColor, 1);
    tg.fillRect(0, 0, 32, 32);
    tg.lineStyle(2, darkerHex, 1);
    tg.strokeRect(0, 0, 32, 32);
    tg.generateTexture(tKey, 32, 32);

    const bg = this.make.graphics({ add: false });
    bg.fillStyle(0x777777, 1);
    bg.fillRect(0, 0, 28, 8);
    bg.lineStyle(1, 0x555555, 1);
    bg.strokeRect(0, 0, 28, 8);
    bg.generateTexture(bKey, 28, 8);

    const tank = this.add.image(data.x, data.y, tKey).setDepth(1);
    if (data.scale && data.scale > 1) tank.setScale(data.scale);
    if (!data.alive) tank.setVisible(false);

    const barrel = this.add.image(data.x, data.y, bKey).setOrigin(0, 0.5).setDepth(2);
    barrel.rotation = data.angle || 0;
    if (data.scale && data.scale > 1) barrel.setScale(data.scale);
    if (!data.alive) barrel.setVisible(false);

    const nameTag = this.add.text(data.x, data.y - 36, data.username || '???', {
      fontFamily: 'Courier New', fontSize: '11px', color: '#333',
    }).setOrigin(0.5).setDepth(51);
    if (!data.alive) nameTag.setVisible(false);

    this.otherPlayers[pid] = {
      tank, barrel, nameTag,
      hp: data.hp, alive: data.alive,
      targetX: data.x, targetY: data.y, targetAngle: data.angle || 0,
    };
  }

  removeRemotePlayer(pid) {
    const r = this.otherPlayers[pid];
    if (r) {
      r.tank.destroy(); r.barrel.destroy();
      if (r.nameTag) r.nameTag.destroy();
      delete this.otherPlayers[pid];
    }
  }
  clearAllRemotePlayers() {
    for (const pid of Object.keys(this.otherPlayers)) this.removeRemotePlayer(pid);
  }
  updateStatus() {
    const count = Object.keys(this.otherPlayers).length + 1;
    this.statusText.setText('Players: ' + count);
  }

  spawnBullet(x, y, angle, shooterId) {
    const bullet = this.bullets.create(x, y, 'bullet');
    bullet.setCircle(4);
    bullet.setVelocity(Math.cos(angle) * 400, Math.sin(angle) * 400);
    bullet.setData('shooter', shooterId);
    this.time.delayedCall(1500, () => { if (bullet.active) bullet.destroy(); });
  }

  checkBulletHits() {
    this.bullets.getChildren().forEach(bullet => {
      if (!bullet.active) return;
      const shooter = bullet.getData('shooter');
      if (shooter === this.myId) {
        for (const [pid, remote] of Object.entries(this.otherPlayers)) {
          if (!remote.alive) continue;
          const dist = Phaser.Math.Distance.Between(bullet.x, bullet.y, remote.tank.x, remote.tank.y);
          if (dist < 22) {
            bullet.destroy();
            this.socket.emit('hit', { target_id: pid });
            return;
          }
        }
      }
      if (shooter && shooter !== this.myId && this.alive && this.tank) {